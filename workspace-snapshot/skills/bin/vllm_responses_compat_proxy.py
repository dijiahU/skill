#!/usr/bin/env python3
"""Adapt Codex Responses requests for local OpenAI-compatible vLLM servers."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route


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
            print(json.dumps({"stage": "responses_context_budget", "failure": type(exc).__name__}), file=sys.stderr, flush=True)
            return JSONResponse({"error": {
                "type": "invalid_request_error" if isinstance(exc, ContextBudgetError) else "server_error",
                "code": "context_length_exceeded" if isinstance(exc, ContextBudgetError) else "token_count_unavailable",
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
        response_headers = {
            name: value for name, value in upstream_response.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS | {"content-encoding"}
        }
        try:
            response_payload = upstream_response.json()
        except (ValueError, UnicodeDecodeError):
            response_payload = None
        await upstream_response.aclose()
        if not (upstream_response.is_success and _is_completed_responses_result(response_payload)):
            return Response(raw_body, status_code=status_code, headers=response_headers)
        return StreamingResponse(
            _emulate_responses_stream(response_payload),
            status_code=status_code,
            media_type="text/event-stream",
        )

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
