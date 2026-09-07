#!/usr/bin/env python3
"""Adapt Codex Responses requests for local OpenAI-compatible vLLM servers."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route


STREAM_CAPTURE_MAX_BYTES = 16 * 1024 * 1024
STREAM_CAPTURE_MAX_FILES = 256


def _stream_diagnostic(**fields) -> None:
    try:
        print(json.dumps({"stage": "responses_emulate_stream", **fields}, ensure_ascii=False, separators=(",", ":")), file=sys.stderr, flush=True)
    except Exception:
        pass


def _capture_emulated_exchange(request_body: bytes, upstream_body: bytes, request_sha256: str, upstream_body_sha256: str) -> str | None:
    directory_name = os.environ.get("SABER_RESPONSES_STREAM_CAPTURE_DIR")
    if not directory_name:
        return None
    if len(request_body) + len(upstream_body) > STREAM_CAPTURE_MAX_BYTES:
        _stream_diagnostic(phase="capture_skipped", reason="byte_limit", request_sha256=request_sha256, upstream_body_sha256=upstream_body_sha256)
        return None
    try:
        directory = Path(directory_name)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if sum(1 for item in directory.iterdir() if item.is_file()) >= STREAM_CAPTURE_MAX_FILES:
            _stream_diagnostic(phase="capture_skipped", reason="file_limit", request_sha256=request_sha256, upstream_body_sha256=upstream_body_sha256)
            return None
        document = {
            "request_sha256": request_sha256,
            "upstream_body_sha256": upstream_body_sha256,
            "request_json": json.loads(request_body),
            "upstream_json": json.loads(upstream_body),
            "request_body_utf8": request_body.decode("utf-8"),
            "upstream_body_utf8": upstream_body.decode("utf-8"),
        }
        encoded = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        if len(encoded) > STREAM_CAPTURE_MAX_BYTES:
            _stream_diagnostic(phase="capture_skipped", reason="encoded_byte_limit", request_sha256=request_sha256, upstream_body_sha256=upstream_body_sha256)
            return None
        path = directory / f"{request_sha256}-{upstream_body_sha256}-{os.getpid()}-{uuid.uuid4().hex}.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(encoded)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return str(path)
    except Exception as exc:
        _stream_diagnostic(phase="capture_failed", failure=type(exc).__name__, request_sha256=request_sha256, upstream_body_sha256=upstream_body_sha256)
        return None


HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _message_text(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        part["text"]
        for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]


def _adapt_responses_payload(
    payload: dict, temperature: float | None = None
) -> tuple[dict, list[str]]:
    """Remove Codex-only fields without overriding model sampling defaults."""
    removed_tools: list[str] = []
    request_input = payload.get("input")
    if isinstance(request_input, list):
        retained_input = []
        developer_texts = []
        for item in request_input:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "message" and item.get("role") == "assistant":
                    item.setdefault("status", "completed")
                    for part in item.get("content", []):
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            part.setdefault("annotations", [])
                elif item_type in {"reasoning", "function_call"}:
                    item.setdefault("status", "completed")
                if item.get("role") == "developer":
                    developer_texts.extend(_message_text(item.get("content")))
                    continue
            retained_input.append(item)
        payload["input"] = retained_input
        if developer_texts:
            existing = payload.get("instructions")
            sections = [existing] if isinstance(existing, str) and existing else []
            sections.extend(developer_texts)
            payload["instructions"] = "\n\n".join(sections)

    tools = payload.get("tools")
    if isinstance(tools, list):
        retained_tools = []
        for tool in tools:
            if isinstance(tool, dict) and tool.get("type") in {
                "namespace",
                "web_search",
                "web_search_preview",
            }:
                removed_tools.append(
                    str(tool.get("name") or tool.get("type") or "<unnamed>")
                )
            else:
                retained_tools.append(tool)
        payload["tools"] = retained_tools

    if temperature is not None:
        payload["temperature"] = temperature

    return payload, removed_tools


def _sse_event(event_type: str, sequence_number: int, **fields) -> bytes:
    data = {"type": event_type, "sequence_number": sequence_number, **fields}
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    ).encode("utf-8")


def _is_completed_responses_result(payload: object) -> bool:
    """Only replay a complete Responses object, never an error or partial result."""
    if not (
        isinstance(payload, dict)
        and payload.get("object") == "response"
        and isinstance(payload.get("id"), str)
        and payload["id"]
        and payload.get("status") == "completed"
        and payload.get("error") is None
        and isinstance(payload.get("output"), list)
    ):
        return False
    for item in payload["output"]:
        if not isinstance(item, dict):
            return False
        if item.get("type") == "function_call" and not isinstance(item.get("arguments"), str):
            return False
        if item.get("type") == "message":
            if not isinstance(item.get("content"), list):
                return False
            for part in item["content"]:
                if not isinstance(part, dict):
                    return False
                if part.get("type") == "output_text" and not isinstance(part.get("text"), str):
                    return False
    return True


def _is_noncompleted_terminal_result(payload: object) -> bool:
    """Accept only genuine failed/incomplete Responses terminal objects."""
    if not (
        isinstance(payload, dict)
        and payload.get("object") == "response"
        and isinstance(payload.get("id"), str)
        and payload["id"]
        and isinstance(payload.get("status"), str)
        and payload["status"] in {"incomplete", "failed"}
        and isinstance(payload.get("output"), list)
    ):
        return False
    if payload["status"] == "failed" and not isinstance(payload.get("error"), dict):
        return False
    if payload["status"] == "incomplete" and not (
        payload.get("error") is None and isinstance(payload.get("incomplete_details"), dict)
    ):
        return False
    for item in payload["output"]:
        if not isinstance(item, dict):
            return False
        if item.get("type") == "function_call":
            arguments = item.get("arguments")
            if arguments is not None and not isinstance(arguments, str):
                return False
        if item.get("type") == "message":
            content = item.get("content")
            if content is not None and not isinstance(content, list):
                return False
    return True


async def _emulate_noncompleted_terminal_stream(response: dict):
    """Emit an explicit failed/incomplete SSE terminal without completing output items."""
    if not _is_noncompleted_terminal_result(response):
        raise ValueError("Only valid failed/incomplete Responses results can be terminal SSE")
    initial = dict(response)
    initial["output"] = []
    initial["status"] = "in_progress"
    initial["usage"] = None
    yield _sse_event("response.created", 0, response=initial)
    yield _sse_event("response.in_progress", 1, response=initial)
    yield _sse_event(f"response.{response['status']}", 2, response=response)


async def _emulate_responses_stream(response: dict):
    """Replay a complete Responses result as standard SSE lifecycle events."""
    if not _is_completed_responses_result(response):
        raise ValueError("Only completed Responses results can be replayed as successful SSE")
    sequence_number = 0
    initial = dict(response)
    initial["output"] = []
    initial["status"] = "in_progress"
    initial["usage"] = None
    yield _sse_event("response.created", sequence_number, response=initial)
    sequence_number += 1
    yield _sse_event("response.in_progress", sequence_number, response=initial)
    sequence_number += 1

    for output_index, item in enumerate(response.get("output", [])):
        item_type = item.get("type")
        item_id = item.get("id")
        if item_type == "function_call":
            added_item = dict(item)
            added_item["arguments"] = ""
            added_item["status"] = "in_progress"
            yield _sse_event(
                "response.output_item.added",
                sequence_number,
                output_index=output_index,
                item=added_item,
            )
            sequence_number += 1
            arguments = item.get("arguments", "")
            yield _sse_event(
                "response.function_call_arguments.delta",
                sequence_number,
                item_id=item_id,
                output_index=output_index,
                delta=arguments,
            )
            sequence_number += 1
            yield _sse_event(
                "response.function_call_arguments.done",
                sequence_number,
                item_id=item_id,
                output_index=output_index,
                name=item.get("name"),
                arguments=arguments,
            )
            sequence_number += 1
        elif item_type == "message":
            added_item = dict(item)
            added_item["content"] = []
            added_item["status"] = "in_progress"
            yield _sse_event(
                "response.output_item.added",
                sequence_number,
                output_index=output_index,
                item=added_item,
            )
            sequence_number += 1
            for content_index, part in enumerate(item.get("content", [])):
                if part.get("type") != "output_text":
                    continue
                empty_part = dict(part)
                empty_part["text"] = ""
                yield _sse_event(
                    "response.content_part.added",
                    sequence_number,
                    item_id=item_id,
                    output_index=output_index,
                    content_index=content_index,
                    part=empty_part,
                )
                sequence_number += 1
                output_text = part.get("text", "")
                yield _sse_event(
                    "response.output_text.delta",
                    sequence_number,
                    item_id=item_id,
                    output_index=output_index,
                    content_index=content_index,
                    delta=output_text,
                    logprobs=[],
                )
                sequence_number += 1
                yield _sse_event(
                    "response.output_text.done",
                    sequence_number,
                    item_id=item_id,
                    output_index=output_index,
                    content_index=content_index,
                    text=output_text,
                    logprobs=[],
                )
                sequence_number += 1
                yield _sse_event(
                    "response.content_part.done",
                    sequence_number,
                    item_id=item_id,
                    output_index=output_index,
                    content_index=content_index,
                    part=part,
                )
                sequence_number += 1
        else:
            yield _sse_event(
                "response.output_item.added",
                sequence_number,
                output_index=output_index,
                item=item,
            )
            sequence_number += 1

        yield _sse_event(
            "response.output_item.done",
            sequence_number,
            output_index=output_index,
            item=item,
        )
        sequence_number += 1

    yield _sse_event("response.completed", sequence_number, response=response)


async def _diagnosed_emulate_responses_stream(response: dict, diagnostic: dict):
    yielded_event_count = 0
    last_yielded_event = None
    terminal_yielded = False
    outcome = "completed"
    failure = None
    try:
        async for chunk in _emulate_responses_stream(response):
            first_line = chunk.split(b"\n", 1)[0]
            if first_line.startswith(b"event: "):
                last_yielded_event = first_line[7:].decode("ascii", errors="replace")
            yielded_event_count += 1
            terminal_yielded = last_yielded_event == "response.completed"
            yield chunk
    except BaseException as exc:
        outcome = "cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "exception"
        failure = type(exc).__name__
        raise
    finally:
        _stream_diagnostic(phase="delivery_final", **diagnostic, yielded_event_count=yielded_event_count, last_yielded_event=last_yielded_event, terminal_yielded=terminal_yielded, outcome=outcome, failure=failure)


async def _diagnosed_emulate_noncompleted_stream(response: dict, diagnostic: dict):
    yielded_event_count = 0
    last_yielded_event = None
    terminal_yielded = False
    outcome = response.get("status", "noncompleted")
    failure = None
    try:
        async for chunk in _emulate_noncompleted_terminal_stream(response):
            first_line = chunk.split(b"\n", 1)[0]
            if first_line.startswith(b"event: "):
                last_yielded_event = first_line[7:].decode("ascii", errors="replace")
            yielded_event_count += 1
            terminal_yielded = last_yielded_event in {"response.incomplete", "response.failed"}
            yield chunk
    except BaseException as exc:
        outcome = "cancelled" if isinstance(exc, (asyncio.CancelledError, GeneratorExit)) else "exception"
        failure = type(exc).__name__
        raise
    finally:
        _stream_diagnostic(phase="delivery_final", **diagnostic, yielded_event_count=yielded_event_count, last_yielded_event=last_yielded_event, terminal_yielded=terminal_yielded, outcome=outcome, failure=failure)


async def forward(request: Request) -> StreamingResponse:
    body = await request.body()
    removed_tools: list[str] = []
    emulate_responses_stream = False
    if request.url.path.endswith("/responses") and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            payload, removed_tools = _adapt_responses_payload(
                payload, request.app.state.temperature
            )
            emulate_responses_stream = (
                request.app.state.emulate_stream and payload.get("stream") is True
            )
            if emulate_responses_stream:
                payload["stream"] = False
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if removed_tools:
                with open(
                    "/2024233123/skills/tmp/last-codex-responses-request.json",
                    "w",
                    encoding="utf-8",
                ) as debug_file:
                    json.dump(payload, debug_file, ensure_ascii=False, indent=2)

    if removed_tools:
        print(
            "filtered unsupported tools: " + ", ".join(removed_tools),
            file=sys.stderr,
            flush=True,
        )

    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }
    upstream_url = (
        request.app.state.upstream.rstrip("/")
        + request.url.path
        + (f"?{request.url.query}" if request.url.query else "")
    )
    if os.environ.get("SABER_RESPONSES_CONTEXT_GUARD") == "1" and request.url.path.endswith("/responses") and body:
        from saber_responses_budget import ContextBudgetError, guard_request
        try:
            body, budget_metadata = await guard_request(
                request.app.state.client, request.app.state.upstream, body, headers)
            print(json.dumps({"stage": "responses_context_budget", **budget_metadata}), file=sys.stderr, flush=True)
        except (ContextBudgetError, ValueError, httpx.HTTPError) as exc:
            print(json.dumps({"stage": "responses_context_budget", "failure": type(exc).__name__, "message": str(exc) if isinstance(exc, ContextBudgetError) else None, "request_sha256": getattr(exc, "request_sha256", None), "upstream_status": getattr(exc, "upstream_status", None), "upstream_body_sha256": getattr(exc, "upstream_body_sha256", None)}), file=sys.stderr, flush=True)
            return JSONResponse({"error": {
                "type": "invalid_request_error" if isinstance(exc, ContextBudgetError) else "server_error",
                "code": getattr(exc, "code", "context_length_exceeded") if isinstance(exc, ContextBudgetError) else "token_count_unavailable",
                "message": str(exc) if isinstance(exc, ContextBudgetError) else "Exact Responses token counting is unavailable; generation was not submitted.",
            }}, status_code=400 if isinstance(exc, ContextBudgetError) else 503)

    upstream_request = request.app.state.client.build_request(
        request.method,
        upstream_url,
        headers=headers,
        content=body,
    )
    upstream_response = await request.app.state.client.send(
        upstream_request, stream=not emulate_responses_stream
    )

    if emulate_responses_stream:
        # Preserve failed/incomplete upstream responses, including non-JSON errors.
        # Never synthesize a successful completion from a partial result.
        status_code = upstream_response.status_code
        raw_body = upstream_response.content
        request_sha256 = hashlib.sha256(body).hexdigest()
        upstream_body_sha256 = hashlib.sha256(raw_body).hexdigest()
        response_headers = {
            name: value for name, value in upstream_response.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS | {"content-encoding"}
        }
        try:
            response_payload = upstream_response.json()
        except (ValueError, UnicodeDecodeError):
            response_payload = None
        await upstream_response.aclose()
        output_types = (
            [item.get("type") if isinstance(item, dict) else None for item in response_payload.get("output", [])]
            if isinstance(response_payload, dict) and isinstance(response_payload.get("output"), list)
            else None
        )
        completed_result = upstream_response.is_success and _is_completed_responses_result(response_payload)
        capture_path = None
        if isinstance(response_payload, dict):
            capture_path = _capture_emulated_exchange(body, raw_body, request_sha256, upstream_body_sha256)
        diagnostic = {
            "request_sha256": request_sha256,
            "upstream_body_sha256": upstream_body_sha256,
            "upstream_status": status_code,
            "response_status": response_payload.get("status") if isinstance(response_payload, dict) else None,
            "output_types": output_types,
            "completed_result": completed_result,
            "capture_path": capture_path,
        }
        _stream_diagnostic(phase="upstream_complete", **diagnostic)
        if completed_result:
            return StreamingResponse(
                _diagnosed_emulate_responses_stream(response_payload, diagnostic),
                status_code=status_code,
                media_type="text/event-stream",
            )
        if upstream_response.is_success and _is_noncompleted_terminal_result(response_payload):
            return StreamingResponse(
                _diagnosed_emulate_noncompleted_stream(response_payload, diagnostic),
                status_code=status_code,
                media_type="text/event-stream",
            )
        if not upstream_response.is_success:
            return Response(raw_body, status_code=status_code, headers=response_headers)
        # A successful HTTP status with a malformed/nonterminal object cannot
        # satisfy a streaming Responses request. Preserve its body for diagnosis
        # while making the protocol failure explicit.
        return Response(raw_body, status_code=502, headers=response_headers)

    response_headers = {
        name: value
        for name, value in upstream_response.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }

    async def response_body():
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        response_body(),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


def create_app(
    upstream: str,
    emulate_stream: bool = False,
    temperature: float | None = None,
) -> Starlette:
    app = Starlette(routes=[Route("/{path:path}", forward, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])])
    app.state.upstream = upstream
    app.state.emulate_stream = emulate_stream
    app.state.temperature = temperature
    app.state.client = httpx.AsyncClient(timeout=None, trust_env=False)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument(
        "--emulate-stream",
        action="store_true",
        help="request complete Responses output upstream and replay it as SSE",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="override the upstream sampling temperature",
    )
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.upstream, args.emulate_stream, args.temperature),
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
