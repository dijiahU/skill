#!/usr/bin/env python3
"""Keep gpt-oss Responses streaming while adapting Codex-only request fields."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route


HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "server",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
DEBUG_REQUEST = "/2024233123/skills/tmp/last-codex-gptoss-responses-request.json"


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


def _adapt_responses_payload(payload: dict) -> tuple[dict, list[str]]:
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
                    stable_payload = json.dumps(
                        item, ensure_ascii=False, sort_keys=True
                    ).encode("utf-8")
                    item.setdefault(
                        "id", f"msg_{hashlib.sha256(stable_payload).hexdigest()[:24]}"
                    )
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

    return payload, removed_tools


class ResponsesStreamAudit:
    """Observe complete SSE lines without decoding or changing forwarded chunks."""

    def __init__(self):
        self.pending = b""
        self.terminal = None
        self.byte_count = 0
        self.digest = hashlib.sha256()
        self.replacement_characters = 0
        self.event_counts = {}
        self.output_text_delta_chars = 0
        self.terminal_response = None

    def feed(self, chunk: bytes):
        self.byte_count += len(chunk)
        self.digest.update(chunk)
        self.pending += chunk
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            line = line.rstrip(b"\r")
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                continue
            payload = json.loads(data.decode("utf-8", errors="strict"))
            self.replacement_characters += data.decode("utf-8").count("\ufffd")
            if isinstance(payload, dict):
                kind = payload.get("type")
                if isinstance(kind, str):
                    self.event_counts[kind] = self.event_counts.get(kind, 0) + 1
                delta = payload.get("delta")
                if kind == "response.output_text.delta" and isinstance(delta, str):
                    self.output_text_delta_chars += len(delta)
                response = payload.get("response")
                if kind in {"response.completed", "response.failed", "response.incomplete"} and isinstance(response, dict):
                    # Record structure and lengths only; never turn reasoning into
                    # a final answer or change the bytes sent to the consumer.
                    output = response.get("output")
                    items = []
                    for item in output if isinstance(output, list) else []:
                        if not isinstance(item, dict):
                            continue
                        content = item.get("content")
                        text_parts = [part.get("text", "") for part in content
                                      if isinstance(part, dict) and part.get("type") == "output_text"
                                      and isinstance(part.get("text"), str)] if isinstance(content, list) else []
                        items.append({"type": item.get("type"), "status": item.get("status"),
                                      "role": item.get("role"), "phase": item.get("phase"),
                                      "output_text_chars": sum(map(len, text_parts))})
                    self.terminal_response = {"id": response.get("id"), "status": response.get("status"),
                                              "output_items": items, "usage": response.get("usage"),
                                              "incomplete_details": response.get("incomplete_details")}
            if isinstance(payload, dict) and payload.get("type") in {
                "response.completed", "response.failed", "response.incomplete", "error",
            }:
                self.terminal = payload["type"]
        if len(self.pending) > 16 * 1024 * 1024:
            raise ValueError("Responses SSE line exceeded the diagnostic bound")

    def report(self, failure=None):
        return {"stage": "upstream_responses_stream", "bytes": self.byte_count,
                "sha256": self.digest.hexdigest(), "terminal_event": self.terminal,
                "replacement_characters": self.replacement_characters,
                "failure": failure, "event_counts": self.event_counts,
                "output_text_delta_chars": self.output_text_delta_chars,
                "terminal_response": self.terminal_response}


class ResponsesTerminalRewriter:
    """Rewrite only contradictory terminal SSE frames."""

    MAX_FRAME_BYTES = 16 * 1024 * 1024
    SUPPORTED_TERMINALS = {
        "completed": "response.completed",
        "failed": "response.failed",
        "incomplete": "response.incomplete",
    }

    def __init__(self):
        self.pending = b""
        self.rewrites = []
        self.deferred_error = None

    @staticmethod
    def _split_frame(data: bytes):
        lf = data.find(b"\n\n")
        crlf = data.find(b"\r\n\r\n")
        choices = [(index, delimiter) for index, delimiter in (
            (lf, b"\n\n"), (crlf, b"\r\n\r\n")) if index >= 0]
        if not choices:
            return None
        index, delimiter = min(choices, key=lambda choice: choice[0])
        end = index + len(delimiter)
        return data[:end], data[end:]

    def _rewrite_frame(self, frame: bytes) -> bytes:
        data_lines = list(re.finditer(rb"(?m)^data:[^\r\n]*(?:\r?\n|$)", frame))
        if len(data_lines) != 1:
            return frame
        data_line = data_lines[0]
        raw_line = data_line.group(0)
        raw_data = raw_line.rstrip(b"\r\n")[5:].strip()
        if raw_data == b"[DONE]":
            return frame
        try:
            payload = json.loads(raw_data.decode("utf-8", errors="strict"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return frame
        if not isinstance(payload, dict) or payload.get("type") != "response.completed":
            return frame
        response = payload.get("response")
        status = response.get("status") if isinstance(response, dict) else None
        expected = self.SUPPORTED_TERMINALS.get(status) if isinstance(status, str) else None
        if expected == "response.completed":
            return frame
        if expected is None:
            downstream = {
                "type": "error",
                "code": "unsupported_upstream_terminal_status",
                "message": f"Upstream response ended with unsupported status: {status!r}.",
                "param": None,
            }
            target = "error"
        else:
            downstream = dict(payload)
            downstream["type"] = expected
            target = expected
        self.rewrites.append({
            "upstream_event": "response.completed",
            "upstream_status": status,
            "downstream_event": target,
        })
        ending = raw_line[len(raw_line.rstrip(b"\r\n")):]
        replacement = (b"data: " + json.dumps(downstream, ensure_ascii=False).encode("utf-8")
                       + ending)
        rewritten = frame[:data_line.start()] + replacement + frame[data_line.end():]

        def replace_event(match):
            event_line = match.group(0)
            event_ending = event_line[len(event_line.rstrip(b"\r\n")):]
            return b"event: " + target.encode("ascii") + event_ending

        return re.sub(rb"(?m)^event:[^\r\n]*(?:\r?\n|$)", replace_event, rewritten)

    def feed(self, chunk: bytes) -> list[bytes]:
        self.pending += chunk
        output = []
        while True:
            split = self._split_frame(self.pending)
            if split is None:
                break
            frame, self.pending = split
            if len(frame) > self.MAX_FRAME_BYTES:
                output.append(frame)
                self.deferred_error = ValueError(
                    "Responses SSE frame exceeded the forwarding bound")
                break
            output.append(self._rewrite_frame(frame))
        if len(self.pending) > self.MAX_FRAME_BYTES:
            self.deferred_error = ValueError(
                "Responses SSE frame exceeded the forwarding bound")
        return output

    def flush_partial(self) -> bytes:
        partial, self.pending = self.pending, b""
        return partial

    def report(self):
        return {
            "stage": "downstream_terminal_rewrite",
            "rewrite_count": len(self.rewrites),
            "rewrites": self.rewrites,
        }


async def _forward_responses_stream(upstream_response, request_body=None):
    audit = ResponsesStreamAudit()
    rewriter = ResponsesTerminalRewriter()
    failure = None
    capture_dir = os.environ.get("SABER_RESPONSES_STREAM_CAPTURE_DIR")
    captured = bytearray()
    capture_limit = 16 * 1024 * 1024
    capture_truncated = False
    request_sha256 = hashlib.sha256(request_body).hexdigest() if request_body is not None else None
    try:
        async for chunk in upstream_response.aiter_raw():
            if capture_dir:
                available = max(0, capture_limit - len(captured))
                captured.extend(chunk[:available])
                capture_truncated |= len(chunk) > available
            for output in rewriter.feed(chunk):
                yield output
            audit.feed(chunk)
            if rewriter.deferred_error is not None:
                raise rewriter.deferred_error
        if audit.terminal is None or audit.pending.strip() or rewriter.pending:
            raise ValueError("Responses stream ended without a complete terminal event")
    except (httpx.TransportError, ValueError, UnicodeDecodeError) as exc:
        failure = type(exc).__name__
        partial = rewriter.flush_partial()
        if partial:
            yield partial
        # Do not replay generation after partial tool output. Make the transport
        # failure explicit and retain all bytes already sent to the consumer.
        error = {"type": "error", "code": "upstream_stream_incomplete",
                 "message": "Upstream Responses stream interrupted; partial output retained.",
                 "param": None}
        yield b"\n\nevent: error\ndata: " + json.dumps(error).encode("utf-8") + b"\n\n"
    finally:
        report = audit.report(failure)
        report["request_sha256"] = request_sha256
        report["downstream_rewrite"] = rewriter.report()
        if capture_dir:
            try:
                directory = Path(capture_dir)
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / (uuid.uuid4().hex + ".json")
                request_capture = request_body[:capture_limit] if request_body is not None else b""
                evidence = {"schema_version": 1, "audit": dict(report),
                            "request_base64": base64.b64encode(request_capture).decode("ascii"),
                            "request_truncated": request_body is not None and len(request_body) > capture_limit,
                            "upstream_sse_base64": base64.b64encode(captured).decode("ascii"),
                            "stream_truncated": capture_truncated}
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as output:
                    json.dump(evidence, output)
                report["capture_path"] = str(path)
            except OSError as exc:
                report["capture_error"] = type(exc).__name__
        print(json.dumps(report), file=sys.stderr, flush=True)
        await upstream_response.aclose()


async def forward(request: Request) -> StreamingResponse:
    body = await request.body()
    removed_tools: list[str] = []
    if request.url.path.endswith("/responses") and body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            payload, removed_tools = _adapt_responses_payload(payload)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if removed_tools:
                with open(DEBUG_REQUEST, "w", encoding="utf-8") as debug_file:
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
        upstream_request, stream=True
    )
    response_headers = {
        name: value
        for name, value in upstream_response.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }

    async def response_body():
        is_responses_sse = (
            request.url.path.endswith("/responses")
            and upstream_response.is_success
            and "text/event-stream" in upstream_response.headers.get("content-type", "")
            and not upstream_response.headers.get("content-encoding")
        )
        if is_responses_sse:
            async for chunk in _forward_responses_stream(upstream_response, body):
                yield chunk
            return
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


def create_app(upstream: str) -> Starlette:
    app = Starlette(
        routes=[
            Route(
                "/{path:path}",
                forward,
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            )
        ]
    )
    app.state.upstream = upstream
    app.state.client = httpx.AsyncClient(timeout=None, trust_env=False)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--upstream", required=True)
    args = parser.parse_args()
    uvicorn.run(create_app(args.upstream), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
