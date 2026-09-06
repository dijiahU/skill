#!/usr/bin/env python3
"""Keep gpt-oss Responses streaming while adapting Codex-only request fields."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

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
                "failure": failure}


async def _forward_responses_stream(upstream_response):
    audit = ResponsesStreamAudit()
    failure = None
    try:
        async for chunk in upstream_response.aiter_raw():
            audit.feed(chunk)
            yield chunk
        if audit.terminal is None or audit.pending.strip():
            raise ValueError("Responses stream ended without a complete terminal event")
    except (httpx.TransportError, ValueError, UnicodeDecodeError) as exc:
        failure = type(exc).__name__
        # Do not replay generation after partial tool output. Make the transport
        # failure explicit and retain all bytes already sent to the consumer.
        error = {"type": "error", "code": "upstream_stream_incomplete",
                 "message": "Upstream Responses stream interrupted; partial output retained.",
                 "param": None}
        yield b"\n\nevent: error\ndata: " + json.dumps(error).encode("utf-8") + b"\n\n"
    finally:
        print(json.dumps(audit.report(failure)), file=sys.stderr, flush=True)
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
            async for chunk in _forward_responses_stream(upstream_response):
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
