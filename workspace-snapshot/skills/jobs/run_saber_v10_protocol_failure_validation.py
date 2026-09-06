#!/usr/bin/env python3
"""Offline fault-injection checks for the SABER v10 protocol boundary.

This runner deliberately uses the live Responses compatibility proxy and the
live Codex native adapter with controlled in-memory transports.  It produces
implementation evidence for three failure contracts without claiming that any
real model service exhibited the injected faults.  It never starts a model,
Docker container, or GPU job.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import platform
from pathlib import Path
import sys
from types import SimpleNamespace
import types
from typing import Any
from unittest.mock import patch

import httpx


ROOT = Path("/2024233123/skills")
REPORT_ROOT = ROOT / "reports/v10-fixes-20260906"
DEFAULT_OUTPUT = REPORT_ROOT / "protocol-failure-validation-local"
ADAPTER_ROOT = ROOT / "projects/skill/saber"
ADAPTER_PATH = ADAPTER_ROOT / "harness_adapters/codex_native_adapter.py"
PROXY_PATH = ROOT / "bin/vllm_responses_compat_proxy.py"
GLM_PROXY_PATH = ROOT / "bin/vllm_responses_compat_proxy_glm47.py"
GPTOSS_PROXY_PATH = ROOT / "bin/vllm_responses_compat_proxy_gptoss.py"
MODELS = ("mistral", "minimax", "deepseek_flash", "glm", "gptoss")
FIXTURE_CORPUS_SHA256 = (
    "3dbba088b71153d5af02ef081376d83017f87da8cf1142c81764e19a0ac56167"
)
PROTOCOL_VERSION = "saber-v10-responses-budget-v1"

INVALID_PROBE = "invalid_tool_json_not_executed_and_valid_retry"
STREAM_PROBE = "stream_disconnect_preserves_partial_without_duplicate_tool_execution"
COMPLETION_PROBE = "completed_requires_nonempty_model_final"
REQUIRED_CHECKS = {
    INVALID_PROBE: ("invalid_not_executed", "valid_retry_exactly_once"),
    STREAM_PROBE: (
        "partial_preserved",
        "no_duplicate_tool_execution",
        "terminal_consistent",
    ),
    COMPLETION_PROBE: (
        "completed_has_nonempty_model_final",
        "synthetic_completion_rejected",
    ),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(pending, path)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalRequest:
    """The subset of Starlette Request consumed by the real proxy forwarder."""

    def __init__(self, scope: dict[str, Any], receive: Any) -> None:
        self.method = scope["method"]
        self.url = SimpleNamespace(
            path=scope["path"], query=scope.get("query_string", b"").decode()
        )
        self.headers = {
            key.decode(): value.decode() for key, value in scope.get("headers", [])
        }
        self.app = scope["app"]
        self._receive = receive

    async def body(self) -> bytes:
        chunks = bytearray()
        while True:
            event = await self._receive()
            chunks.extend(event.get("body", b""))
            if not event.get("more_body"):
                return bytes(chunks)


def install_proxy_dependency_shims() -> list[str]:
    """Install transport-only shims when this host lacks proxy web packages.

    The exercised validation, replay, and forward functions still come from
    the live proxy source. These shims only supply response containers and app
    declarations normally supplied by Starlette/Uvicorn in the serving image.
    """

    shims: list[str] = []
    try:
        import starlette  # noqa: F401
    except ModuleNotFoundError:
        starlette = types.ModuleType("starlette")
        applications = types.ModuleType("starlette.applications")
        requests = types.ModuleType("starlette.requests")
        responses = types.ModuleType("starlette.responses")
        routing = types.ModuleType("starlette.routing")

        class Response:
            def __init__(
                self,
                content: bytes | str = b"",
                status_code: int = 200,
                headers: dict[str, str] | None = None,
                media_type: str | None = None,
            ) -> None:
                self.body = content.encode() if isinstance(content, str) else content
                self.status_code = status_code
                self.headers = httpx.Headers(headers or {})
                if media_type and "content-type" not in self.headers:
                    self.headers["content-type"] = media_type

        class JSONResponse(Response):
            def __init__(self, content: Any, status_code: int = 200) -> None:
                super().__init__(
                    json.dumps(content, ensure_ascii=False).encode(),
                    status_code,
                    {"content-type": "application/json"},
                )

        class StreamingResponse(Response):
            def __init__(
                self,
                content: Any,
                status_code: int = 200,
                headers: dict[str, str] | None = None,
                media_type: str | None = None,
            ) -> None:
                super().__init__(b"", status_code, headers, media_type)
                self.body_iterator = content

        class Starlette:
            def __init__(self, routes: list[Any]) -> None:
                self.routes = routes
                self.state = SimpleNamespace()

        class Route:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.args = args
                self.kwargs = kwargs

        applications.Starlette = Starlette
        requests.Request = LocalRequest
        responses.JSONResponse = JSONResponse
        responses.Response = Response
        responses.StreamingResponse = StreamingResponse
        routing.Route = Route
        sys.modules.update(
            {
                "starlette": starlette,
                "starlette.applications": applications,
                "starlette.requests": requests,
                "starlette.responses": responses,
                "starlette.routing": routing,
            }
        )
        shims.append("starlette_response_containers")

    try:
        import uvicorn  # noqa: F401
    except ModuleNotFoundError:
        uvicorn = types.ModuleType("uvicorn")

        def unavailable_run(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("uvicorn serving is outside this offline validator")

        uvicorn.run = unavailable_run
        sys.modules["uvicorn"] = uvicorn
        shims.append("uvicorn_import_only")
    return shims


class FakeRuntime:
    """Minimal real-adapter runtime whose executions are easy to audit."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_tools(self, provider: str) -> list[dict[str, Any]]:
        if provider != "codex":
            raise AssertionError(f"unexpected provider: {provider}")
        return [
            {
                "name": "bash",
                "description": "controlled local inspection",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append({"name": name, "arguments": dict(arguments)})
        return "controlled observation"


class FakeAppServer:
    """Deterministic app-server transcript accepted by the real adapter."""

    def __init__(self, events: list[Any]) -> None:
        self.events = list(events)
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self.read_count = 0

    def request(self, method: str, params: dict[str, Any], deadline: float) -> dict[str, Any]:
        del params, deadline
        if method == "initialize":
            return {"userAgent": "controlled-local-fault-fixture"}
        if method == "skills/list":
            return {"data": []}
        if method == "hooks/list":
            return {}
        if method == "thread/start":
            return {"thread": {"id": "thread-local"}, "instructionSources": []}
        if method == "turn/start":
            return {"turn": {"id": "turn-local"}}
        raise AssertionError(f"unexpected request method: {method}")

    def request_start(self, method: str, params: dict[str, Any]) -> int:
        del method, params
        return 91

    def read(self, deadline: float) -> dict[str, Any]:
        del deadline
        self.read_count += 1
        if not self.events:
            raise AssertionError("fake app-server transcript exhausted")
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def send(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.closed = True


class MemoryBody(httpx.AsyncByteStream):
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.closed = False

    async def __aiter__(self):
        yield self.body

    async def aclose(self) -> None:
        self.closed = True


class InterruptingBody(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        raise httpx.ReadError("controlled upstream stream interruption")

    async def aclose(self) -> None:
        self.closed = True


def tool_call(adapter_module: Any, call_id: str, arguments: Any) -> dict[str, Any]:
    return {
        "id": int(call_id.rsplit("-", 1)[-1]),
        "method": "item/tool/call",
        "params": {
            "tool": adapter_module.SABER_BASH_TOOL,
            "arguments": arguments,
            "callId": call_id,
        },
    }


def agent_message(text: str, phase: str | None = "final_answer") -> dict[str, Any]:
    return {
        "method": "item/completed",
        "params": {"item": {"type": "agentMessage", "phase": phase, "text": text}},
    }


def turn_completed() -> dict[str, Any]:
    return {"method": "turn/completed", "params": {"turn": {"status": "completed"}}}


def run_adapter_transcript(adapter_module: Any, events: list[Any]) -> dict[str, Any]:
    adapter = adapter_module.CodexNativeHarnessAdapter(skill_mode="none", max_steps=8)
    runtime = FakeRuntime()
    server = FakeAppServer(events)
    error: BaseException | None = None
    conversation: list[dict[str, Any]] | None = None
    workspace = REPORT_ROOT / ".local-protocol-fake-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "local_protocol_fault_fixture",
        "setup": {
            "cwd": "/home/user/project",
            "user_prompt": "Inspect the controlled fixture.",
            "file_contents": {},
        },
    }
    model = {"id": "controlled-fake-model", "timeout_seconds": 30}
    with (
        patch.object(
            adapter,
            "_prepare_environment",
            return_value=({}, workspace, None, False),
        ),
        patch.object(adapter_module, "AppServerProcess", return_value=server),
    ):
        try:
            conversation = adapter.run_task("controlled", model, task, runtime)
        except BaseException as exc:  # Evidence records exact protocol failure type.
            error = exc
            conversation = adapter.last_conversation
    return {
        "adapter": adapter,
        "runtime": runtime,
        "server": server,
        "conversation": conversation or [],
        "error": error,
    }


def response_request(app: Any, payload: dict[str, Any]) -> LocalRequest:
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {
            "type": "http.request",
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "more_body": False,
        }

    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/responses",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("controlled.invalid", 80),
        "app": app,
    }
    return LocalRequest(scope, receive)


async def proxy_stream_interruption(proxy: Any) -> dict[str, Any]:
    partial_chunks = [
        b'event: response.created\ndata: {"type":"response.created"}\n\n',
        b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"partial-safe"}\n\n',
    ]
    stream = InterruptingBody(partial_chunks)
    upstream_requests: list[dict[str, Any]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=stream,
            request=request,
        )

    retained = bytearray()
    error: BaseException | None = None
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        app = SimpleNamespace(
            state=SimpleNamespace(
                upstream="http://controlled.invalid",
                client=client,
                emulate_stream=False,
                temperature=None,
            )
        )
        response = await proxy.forward(response_request(app, {"stream": True, "input": []}))
        try:
            async for chunk in response.body_iterator:
                retained.extend(chunk.encode() if isinstance(chunk, str) else chunk)
        except BaseException as exc:
            error = exc
    return {
        "retained": bytes(retained),
        "error": error,
        "stream_closed": stream.closed,
        "upstream_request_count": len(upstream_requests),
        "upstream_requests": upstream_requests,
    }


async def proxy_buffered_interruption(proxy: Any) -> dict[str, Any]:
    """Exercise a proxy that buffers upstream before it can return client bytes."""

    stream = InterruptingBody([b'{"object":"response","status":"in_progress"'])
    upstream_requests: list[dict[str, Any]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=stream,
            request=request,
        )

    response = None
    client_body = b""
    error: BaseException | None = None
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        app = SimpleNamespace(
            state=SimpleNamespace(
                upstream="http://controlled.invalid",
                client=client,
                emulate_stream=True,
                temperature=None,
            )
        )
        try:
            response = await proxy.forward(
                response_request(app, {"stream": True, "input": []})
            )
            if hasattr(response, "body_iterator"):
                parts = [
                    part.encode() if isinstance(part, str) else part
                    async for part in response.body_iterator
                ]
                client_body = b"".join(parts)
            else:
                client_body = response.body
        except BaseException as exc:
            error = exc
    return {
        "client_body": client_body,
        "response_created": response is not None,
        "error": error,
        "stream_closed": stream.closed,
        "upstream_request_count": len(upstream_requests),
        "upstream_requests": upstream_requests,
    }


async def proxy_direct_wire(proxy: Any, wire: bytes) -> dict[str, Any]:
    """Send one complete controlled SSE wire image through a streaming proxy."""

    stream = MemoryBody(wire)
    upstream_requests: list[dict[str, Any]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=stream,
            request=request,
        )

    stderr = io.StringIO()
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        app = SimpleNamespace(
            state=SimpleNamespace(
                upstream="http://controlled.invalid",
                client=client,
                emulate_stream=False,
                temperature=None,
            )
        )
        with contextlib.redirect_stderr(stderr):
            response = await proxy.forward(
                response_request(app, {"stream": True, "input": []})
            )
            parts = [
                part.encode() if isinstance(part, str) else part
                async for part in response.body_iterator
            ]
    return {
        "body": b"".join(parts),
        "stream_closed": stream.closed,
        "upstream_request_count": len(upstream_requests),
        "stderr": stderr.getvalue(),
    }


def sse_event(kind: str, **fields: Any) -> bytes:
    return (
        "data: "
        + json.dumps({"type": kind, **fields}, ensure_ascii=False)
        + "\n\n"
    ).encode("utf-8")


async def proxy_buffered_case(proxy: Any, payload: dict[str, Any]) -> dict[str, Any]:
    stream = MemoryBody(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    upstream_requests: list[dict[str, Any]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=stream,
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        app = SimpleNamespace(
            state=SimpleNamespace(
                upstream="http://controlled.invalid",
                client=client,
                emulate_stream=True,
                temperature=None,
            )
        )
        with contextlib.redirect_stderr(io.StringIO()):
            response = await proxy.forward(
                response_request(app, {"stream": True, "input": []})
            )
        if hasattr(response, "body_iterator"):
            parts = [
                part.encode() if isinstance(part, str) else part
                async for part in response.body_iterator
            ]
            body = b"".join(parts)
        else:
            body = response.body
    return {
        "body": body,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "stream_closed": stream.closed,
        "upstream_request_count": len(upstream_requests),
        "upstream_requests": upstream_requests,
    }


def response_events(body: bytes) -> list[dict[str, Any]]:
    return [
        json.loads(line[6:])
        for line in body.decode("utf-8", errors="strict").splitlines()
        if line.startswith("data: ")
    ]


def assertions_dict(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items()}


def write_case(
    output_dir: Path,
    probe_name: str,
    checks: dict[str, bool],
    assertions: dict[str, Any],
    source_sha256: dict[str, str],
    error: BaseException | None = None,
    model_applicability: dict[str, str] | None = None,
) -> dict[str, Any]:
    required = REQUIRED_CHECKS[probe_name]
    normalized = {name: checks.get(name) is True for name in required}
    passed = all(normalized.values()) and error is None
    evidence_path = (output_dir / f"{probe_name}.json").resolve()
    evidence = {
        "schema_version": 1,
        "scope": "controlled_local_fault_injection",
        "probe_name": probe_name,
        "passed": passed,
        "checks": normalized,
        "assertions": assertions,
        "error": None
        if error is None
        else {"type": type(error).__name__, "message": str(error)},
        "source_sha256": source_sha256,
        "model_applicability": model_applicability or {},
        "real_model_service_invoked": False,
    }
    save_json(evidence_path, evidence)
    return {
        "probe_name": probe_name,
        "passed": passed,
        "checks": normalized,
        "evidence_paths": [str(evidence_path)],
        "source_sha256": source_sha256,
        "model_applicability": model_applicability or {},
    }


def invalid_tool_case(adapter_module: Any, output_dir: Path, sources: dict[str, str]) -> dict[str, Any]:
    malformed = '{"command":"inspect controlled",}'
    run = run_adapter_transcript(
        adapter_module,
        [
            tool_call(adapter_module, "call-1", malformed),
            tool_call(adapter_module, "call-2", {"command": "inspect controlled"}),
            agent_message("Controlled inspection finished."),
            turn_completed(),
        ],
    )
    adapter = run["adapter"]
    runtime = run["runtime"]
    server = run["server"]
    responses = [item for item in server.sent if item.get("id") in {1, 2}]
    invalid_responses = [item for item in responses if item.get("id") == 1]
    valid_responses = [item for item in responses if item.get("id") == 2]
    diagnostics = adapter.last_run_meta.get("tool_argument_errors", [])
    invalid_not_executed = (
        len(runtime.calls) == 1
        and runtime.calls[0] == {
            "name": "bash",
            "arguments": {"command": "inspect controlled"},
        }
        and len(diagnostics) == 1
        and diagnostics[0].get("raw_arguments") == malformed
        and len(invalid_responses) == 1
        and invalid_responses[0].get("result", {}).get("success") is False
    )
    valid_retry_exactly_once = (
        len(valid_responses) == 1
        and valid_responses[0].get("result", {}).get("success") is True
        and adapter.last_run_meta.get("task_tool_attempts") == 2
        and adapter.last_run_meta.get("tool_calls") == 1
        and run["error"] is None
        and server.closed
    )
    assertions = assertions_dict(
        malformed_raw_arguments=malformed,
        runtime_calls=runtime.calls,
        task_tool_attempts=adapter.last_run_meta.get("task_tool_attempts"),
        executed_tool_calls=adapter.last_run_meta.get("tool_calls"),
        argument_error_count=len(diagnostics),
        tool_response_success_by_id={
            str(item["id"]): item.get("result", {}).get("success") for item in responses
        },
        server_closed=server.closed,
        model_final_present=adapter.last_run_meta.get("model_final_present"),
    )
    return write_case(
        output_dir,
        INVALID_PROBE,
        {
            "invalid_not_executed": invalid_not_executed,
            "valid_retry_exactly_once": valid_retry_exactly_once,
        },
        assertions,
        sources,
        run["error"],
        {model: "shared_codex_native_adapter" for model in MODELS},
    )


async def stream_case(
    adapter_module: Any,
    generic_proxy: Any,
    glm_proxy: Any,
    gptoss_proxy: Any,
    output_dir: Path,
    sources: dict[str, str],
) -> dict[str, Any]:
    generic_direct = await proxy_stream_interruption(generic_proxy)
    generic_buffered = await proxy_buffered_interruption(generic_proxy)
    glm_buffered = await proxy_buffered_interruption(glm_proxy)
    gptoss_stream = await proxy_stream_interruption(gptoss_proxy)
    adapter_run = run_adapter_transcript(
        adapter_module,
        [
            tool_call(adapter_module, "call-1", {"command": "inspect partial"}),
            agent_message("Partial diagnostic retained.", phase=None),
            TimeoutError("controlled app-server stream interruption"),
        ],
    )

    direct_retained = generic_direct["retained"]
    gptoss_retained = gptoss_stream["retained"]
    conversation = adapter_run["conversation"]
    runtime = adapter_run["runtime"]
    adapter_partial = (
        any(
            item.get("role") == "tool"
            and item.get("output") == "controlled observation"
            for item in conversation
        )
        and any(
            item.get("role") == "assistant"
            and item.get("content") == "Partial diagnostic retained."
            for item in conversation
        )
    )
    generic_direct_ok = (
        b"partial-safe" in direct_retained
        and isinstance(generic_direct["error"], httpx.ReadError)
        and b"response.completed" not in direct_retained
        and generic_direct["stream_closed"]
    )
    generic_buffered_ok = (
        generic_buffered["client_body"] == b""
        and generic_buffered["response_created"] is False
        and isinstance(generic_buffered["error"], httpx.ReadError)
        and b"response.completed" not in generic_buffered["client_body"]
        and generic_buffered["stream_closed"]
    )
    glm_buffered_ok = (
        glm_buffered["client_body"] == b""
        and glm_buffered["response_created"] is False
        and isinstance(glm_buffered["error"], httpx.ReadError)
        and b"response.completed" not in glm_buffered["client_body"]
        and glm_buffered["stream_closed"]
    )
    gptoss_stream_ok = (
        b"partial-safe" in gptoss_retained
        and gptoss_stream["error"] is None
        and b"upstream_stream_incomplete" in gptoss_retained
        and b"response.completed" not in gptoss_retained
        and gptoss_stream["stream_closed"]
    )
    partial_preserved = (
        generic_direct_ok
        and generic_buffered_ok
        and glm_buffered_ok
        and gptoss_stream_ok
        and adapter_partial
    )
    no_duplicate_tool_execution = (
        generic_direct["upstream_request_count"] == 1
        and generic_buffered["upstream_request_count"] == 1
        and glm_buffered["upstream_request_count"] == 1
        and gptoss_stream["upstream_request_count"] == 1
        and runtime.calls
        == [{"name": "bash", "arguments": {"command": "inspect partial"}}]
    )
    terminal_consistent = (
        isinstance(adapter_run["error"], TimeoutError)
        and adapter_run["adapter"].last_run_meta.get("turn_status") is None
        and adapter_run["server"].closed
        and generic_direct_ok
        and generic_buffered_ok
        and glm_buffered_ok
        and gptoss_stream_ok
    )
    assertions = assertions_dict(
        model_proxy_matrix={
            "mistral": {
                "path": "generic_direct_stream",
                "partial_forwarded": b"partial-safe" in direct_retained,
                "terminal": type(generic_direct["error"]).__name__
                if generic_direct["error"]
                else None,
                "upstream_requests": generic_direct["upstream_request_count"],
            },
            "minimax": {
                "path": "generic_emulated_buffer",
                "partial_forwarded": bool(generic_buffered["client_body"]),
                "terminal": type(generic_buffered["error"]).__name__
                if generic_buffered["error"]
                else None,
                "upstream_requests": generic_buffered["upstream_request_count"],
            },
            "deepseek_flash": {
                "path": "generic_direct_stream",
                "partial_forwarded": b"partial-safe" in direct_retained,
                "terminal": type(generic_direct["error"]).__name__
                if generic_direct["error"]
                else None,
                "upstream_requests": generic_direct["upstream_request_count"],
            },
            "glm": {
                "path": "glm47_emulated_buffer",
                "partial_forwarded": bool(glm_buffered["client_body"]),
                "terminal": type(glm_buffered["error"]).__name__
                if glm_buffered["error"]
                else None,
                "upstream_requests": glm_buffered["upstream_request_count"],
            },
            "gptoss": {
                "path": "gptoss_audited_stream",
                "partial_forwarded": b"partial-safe" in gptoss_retained,
                "terminal": "explicit_error_sse"
                if b"upstream_stream_incomplete" in gptoss_retained
                else None,
                "upstream_requests": gptoss_stream["upstream_request_count"],
            },
        },
        buffered_semantics=(
            "MiniMax and GLM buffer the upstream response, so interruption before "
            "a complete response exposes no client partial and raises transport failure."
        ),
        generic_direct_partial_sha256=sha256_bytes(direct_retained),
        gptoss_partial_and_error_sha256=sha256_bytes(gptoss_retained),
        adapter_error_type=type(adapter_run["error"]).__name__
        if adapter_run["error"]
        else None,
        adapter_runtime_calls=runtime.calls,
        adapter_conversation=conversation,
        adapter_server_closed=adapter_run["server"].closed,
    )
    unexpected = None
    if (
        generic_direct["error"] is None
        or generic_buffered["error"] is None
        or glm_buffered["error"] is None
        or gptoss_stream["error"] is not None
        or adapter_run["error"] is None
    ):
        unexpected = AssertionError("a controlled stream terminal differed from its proxy contract")
    return write_case(
        output_dir,
        STREAM_PROBE,
        {
            "partial_preserved": partial_preserved,
            "no_duplicate_tool_execution": no_duplicate_tool_execution,
            "terminal_consistent": terminal_consistent,
        },
        assertions,
        sources,
        unexpected,
        {
            "mistral": "generic_direct_stream",
            "minimax": "generic_emulated_buffer",
            "deepseek_flash": "generic_direct_stream",
            "glm": "glm47_emulated_buffer",
            "gptoss": "gptoss_audited_stream",
        },
    )


async def completion_case(
    adapter_module: Any,
    generic_proxy: Any,
    glm_proxy: Any,
    gptoss_proxy: Any,
    output_dir: Path,
    sources: dict[str, str],
) -> dict[str, Any]:
    completed_payload = {
        "object": "response",
        "id": "resp-controlled-complete",
        "status": "completed",
        "error": None,
        "output": [
            {
                "type": "message",
                "id": "msg-controlled",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Controlled final answer.",
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 4, "output_tokens": 4, "total_tokens": 8},
    }
    incomplete_payload = {
        **completed_payload,
        "id": "resp-controlled-incomplete",
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
    }

    generic_buffered_complete = await proxy_buffered_case(
        generic_proxy, completed_payload
    )
    generic_buffered_incomplete = await proxy_buffered_case(
        generic_proxy, incomplete_payload
    )
    glm_complete = await proxy_buffered_case(glm_proxy, completed_payload)
    glm_incomplete = await proxy_buffered_case(glm_proxy, incomplete_payload)

    valid_wire = (
        sse_event("response.output_text.delta", delta="Controlled final answer.")
        + sse_event("response.completed", response={"status": "completed"})
    )
    incomplete_wire = sse_event(
        "response.incomplete",
        response={"status": "incomplete", "incomplete_details": {"reason": "limit"}},
    )
    generic_direct_complete = await proxy_direct_wire(generic_proxy, valid_wire)
    generic_direct_incomplete = await proxy_direct_wire(generic_proxy, incomplete_wire)
    gptoss_complete = await proxy_direct_wire(gptoss_proxy, valid_wire)
    gptoss_incomplete = await proxy_direct_wire(gptoss_proxy, incomplete_wire)

    generic_complete_events = response_events(generic_buffered_complete["body"])
    generic_finals = [
        event
        for event in generic_complete_events
        if event.get("type") == "response.completed"
    ]
    glm_complete_events = response_events(glm_complete["body"])
    glm_finals = [
        event
        for event in glm_complete_events
        if event.get("type") == "response.completed"
    ]
    generic_incomplete_events = response_events(generic_buffered_incomplete["body"])
    glm_incomplete_events = response_events(glm_incomplete["body"])

    adapter_valid = run_adapter_transcript(
        adapter_module,
        [agent_message("Controlled final answer."), turn_completed()],
    )
    adapter_empty = run_adapter_transcript(adapter_module, [turn_completed()])
    empty_error = adapter_empty["error"]
    valid_conversation = adapter_valid["conversation"]

    per_model_completion = {
        "mistral": (
            generic_direct_complete["body"] == valid_wire
            and generic_direct_complete["upstream_request_count"] == 1
        ),
        "minimax": (
            len(generic_finals) == 1
            and generic_finals[0].get("response") == completed_payload
            and generic_buffered_complete["upstream_request_count"] == 1
        ),
        "deepseek_flash": (
            generic_direct_complete["body"] == valid_wire
            and generic_direct_complete["upstream_request_count"] == 1
        ),
        "glm": (
            len(glm_finals) == 1
            and glm_finals[0].get("response") == completed_payload
            and glm_complete["upstream_request_count"] == 1
        ),
        "gptoss": (
            gptoss_complete["body"] == valid_wire
            and gptoss_complete["upstream_request_count"] == 1
            and '"terminal_event": "response.completed"' in gptoss_complete["stderr"]
        ),
    }
    adapter_completed_ok = (
        any(
            item.get("role") == "assistant"
            and item.get("source") == "model"
            and isinstance(item.get("content"), str)
            and item["content"].strip()
            for item in valid_conversation
        )
        and adapter_valid["adapter"].last_run_meta.get("model_final_present") is True
        and adapter_valid["error"] is None
    )
    completed_has_nonempty_model_final = (
        all(per_model_completion.values()) and adapter_completed_ok
    )

    per_model_incomplete = {
        "mistral": (
            generic_direct_incomplete["body"] == incomplete_wire
            and b"response.completed" not in generic_direct_incomplete["body"]
            and generic_direct_incomplete["upstream_request_count"] == 1
        ),
        "minimax": (
            not generic_incomplete_events
            and b"response.completed" not in generic_buffered_incomplete["body"]
            and json.loads(generic_buffered_incomplete["body"]) == incomplete_payload
            and generic_buffered_incomplete["upstream_request_count"] == 1
        ),
        "deepseek_flash": (
            generic_direct_incomplete["body"] == incomplete_wire
            and b"response.completed" not in generic_direct_incomplete["body"]
            and generic_direct_incomplete["upstream_request_count"] == 1
        ),
        "glm": (
            not glm_incomplete_events
            and b"response.completed" not in glm_incomplete["body"]
            and json.loads(glm_incomplete["body"]) == incomplete_payload
            and glm_incomplete["upstream_request_count"] == 1
        ),
        "gptoss": (
            gptoss_incomplete["body"] == incomplete_wire
            and b"response.completed" not in gptoss_incomplete["body"]
            and gptoss_incomplete["upstream_request_count"] == 1
            and '"terminal_event": "response.incomplete"' in gptoss_incomplete["stderr"]
        ),
    }
    adapter_empty_rejected = (
        isinstance(empty_error, adapter_module.AppServerProtocolError)
        and adapter_empty["adapter"].last_run_meta.get("technical_failure_stage")
        == "empty_model_final"
        and adapter_empty["adapter"].last_run_meta.get("model_final_present") is False
        and not any(
            item.get("role") == "assistant"
            and isinstance(item.get("content"), str)
            and item["content"].strip()
            for item in adapter_empty["conversation"]
        )
    )
    synthetic_completion_rejected = (
        all(per_model_incomplete.values()) and adapter_empty_rejected
    )
    assertions = assertions_dict(
        model_proxy_matrix={
            "mistral": {
                "path": "generic_direct_stream",
                "nonempty_completed_preserved": per_model_completion["mistral"],
                "incomplete_preserved_without_completed": per_model_incomplete["mistral"],
            },
            "minimax": {
                "path": "generic_emulated_buffer",
                "nonempty_completed_replayed": per_model_completion["minimax"],
                "incomplete_preserved_without_sse": per_model_incomplete["minimax"],
            },
            "deepseek_flash": {
                "path": "generic_direct_stream",
                "nonempty_completed_preserved": per_model_completion["deepseek_flash"],
                "incomplete_preserved_without_completed": per_model_incomplete[
                    "deepseek_flash"
                ],
            },
            "glm": {
                "path": "glm47_emulated_buffer",
                "nonempty_completed_replayed": per_model_completion["glm"],
                "incomplete_preserved_without_sse": per_model_incomplete["glm"],
            },
            "gptoss": {
                "path": "gptoss_audited_stream",
                "nonempty_completed_preserved": per_model_completion["gptoss"],
                "incomplete_terminal_preserved": per_model_incomplete["gptoss"],
            },
        },
        valid_adapter_model_final_present=adapter_valid[
            "adapter"
        ].last_run_meta.get("model_final_present"),
        valid_adapter_conversation=valid_conversation,
        empty_adapter_error_type=type(empty_error).__name__ if empty_error else None,
        empty_adapter_error_message=str(empty_error) if empty_error else None,
        empty_adapter_failure_stage=adapter_empty["adapter"].last_run_meta.get(
            "technical_failure_stage"
        ),
        empty_adapter_model_final_present=adapter_empty[
            "adapter"
        ].last_run_meta.get("model_final_present"),
        empty_adapter_conversation=adapter_empty["conversation"],
    )
    unexpected = None
    if adapter_valid["error"] is not None or empty_error is None:
        unexpected = AssertionError("completion fixture produced the wrong adapter result")
    return write_case(
        output_dir,
        COMPLETION_PROBE,
        {
            "completed_has_nonempty_model_final": completed_has_nonempty_model_final,
            "synthetic_completion_rejected": synthetic_completion_rejected,
        },
        assertions,
        sources,
        unexpected,
        {
            "mistral": "generic_direct_stream",
            "minimax": "generic_emulated_buffer",
            "deepseek_flash": "generic_direct_stream",
            "glm": "glm47_emulated_buffer",
            "gptoss": "gptoss_audited_stream",
        },
    )


async def run(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to(REPORT_ROOT.resolve()):
        raise ValueError(f"output directory must remain under {REPORT_ROOT}")
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ADAPTER_ROOT))
    adapter_module = importlib.import_module("harness_adapters.codex_native_adapter")
    proxy_dependency_shims = install_proxy_dependency_shims()
    proxy_module = load_module("saber_v10_proxy_fault_target", PROXY_PATH)
    glm_proxy_module = load_module(
        "saber_v10_glm_proxy_fault_target", GLM_PROXY_PATH
    )
    gptoss_proxy_module = load_module(
        "saber_v10_gptoss_proxy_fault_target", GPTOSS_PROXY_PATH
    )
    runner_path = Path(__file__).resolve()
    all_sources = {
        str(runner_path): sha256_file(runner_path),
        str(ADAPTER_PATH.resolve()): sha256_file(ADAPTER_PATH),
        str(PROXY_PATH.resolve()): sha256_file(PROXY_PATH),
        str(GLM_PROXY_PATH.resolve()): sha256_file(GLM_PROXY_PATH),
        str(GPTOSS_PROXY_PATH.resolve()): sha256_file(GPTOSS_PROXY_PATH),
    }
    adapter_sources = {
        path: digest
        for path, digest in all_sources.items()
        if path not in {
            str(PROXY_PATH.resolve()),
            str(GLM_PROXY_PATH.resolve()),
            str(GPTOSS_PROXY_PATH.resolve()),
        }
    }

    cases: list[dict[str, Any]] = []
    runners = (
        (INVALID_PROBE, lambda: invalid_tool_case(adapter_module, output_dir, adapter_sources)),
        (
            STREAM_PROBE,
            lambda: stream_case(
                adapter_module,
                proxy_module,
                glm_proxy_module,
                gptoss_proxy_module,
                output_dir,
                all_sources,
            ),
        ),
        (
            COMPLETION_PROBE,
            lambda: completion_case(
                adapter_module,
                proxy_module,
                glm_proxy_module,
                gptoss_proxy_module,
                output_dir,
                all_sources,
            ),
        ),
    )
    for probe_name, runner in runners:
        try:
            result = runner()
            if asyncio.iscoroutine(result):
                result = await result
            cases.append(result)
        except BaseException as exc:
            cases.append(
                write_case(
                    output_dir,
                    probe_name,
                    {name: False for name in REQUIRED_CHECKS[probe_name]},
                    {"runner_exception": type(exc).__name__},
                    all_sources,
                    exc,
                )
            )

    evidence_paths = sorted(
        {path for case in cases for path in case["evidence_paths"]}
    )
    evidence_sha256 = {path: sha256_file(Path(path)) for path in evidence_paths}
    passed = (
        len(cases) == len(REQUIRED_CHECKS)
        and {case["probe_name"] for case in cases} == set(REQUIRED_CHECKS)
        and all(case["passed"] is True for case in cases)
        and not proxy_dependency_shims
    )
    report = {
        "schema_version": 1,
        "status": "complete" if passed else "failed",
        "passed": passed,
        "scope": "controlled_local_fault_injection",
        "protocol_version": PROTOCOL_VERSION,
        "fixture_corpus_sha256": FIXTURE_CORPUS_SHA256,
        "real_model_service_invoked": False,
        "proxy_host_dependency_shims": proxy_dependency_shims,
        "runtime_environment": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "httpx_version": getattr(httpx, "__version__", None),
            "starlette_version": getattr(sys.modules.get("starlette"), "__version__", None),
            "uvicorn_version": getattr(sys.modules.get("uvicorn"), "__version__", None),
            "native_proxy_dependencies": not proxy_dependency_shims,
        },
        "cases": cases,
        "case_count": len(cases),
        "evidence_paths": evidence_paths,
        "evidence_sha256": evidence_sha256,
        "source_sha256": all_sources,
        "real_model_binding_contract": {
            "proves": (
                "The current live adapter and proxy satisfy these contracts under "
                "controlled local fault injection."
            ),
            "does_not_prove": (
                "No real model or serving stack was invoked, so this report does not "
                "show that a model experienced any injected fault."
            ),
            "aggregate_requirement": (
                "Each of the five real-model protocol cases must also pass against its "
                "actual service and bind every dependency loaded by that service to the "
                "frozen manifest hashes. This local evidence may accompany, but never "
                "replace, those per-model case evidence paths."
            ),
            "aggregation": (
                "For each matching probe_name, union this case evidence path with the "
                "real-model probe evidence paths; retain the real-model checks, model "
                "identity, cleanup_safe result, and frozen source_sha256 binding."
            ),
        },
    }
    save_json(output_dir / "protocol-failure-validation.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = asyncio.run(run(args.output_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
