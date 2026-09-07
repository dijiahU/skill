"""Offline diagnostics checks for generic Responses stream emulation."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import httpx
from starlette.requests import Request


PROXY_PATH = Path(__file__).resolve().parents[2] / "bin/vllm_responses_compat_proxy.py"
SPEC = importlib.util.spec_from_file_location("generic_stream_diagnostics", PROXY_PATH)
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)


def completed_response():
    return {
        "object": "response", "id": "resp_diagnostic", "status": "completed",
        "error": None,
        "output": [{
            "type": "message", "id": "msg_diagnostic", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "ok", "annotations": []}],
        }],
    }


class MemoryBody(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        yield self.content

    async def aclose(self):
        pass


class GenericStreamDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_forward_logs_hashes_status_types_and_capture(self):
        upstream_body = json.dumps(completed_response()).encode()
        sent_bodies = []

        async def upstream(request):
            sent_bodies.append(request.content)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                stream=MemoryBody(upstream_body),
            )

        async def receive():
            return {
                "type": "http.request",
                "body": b'{"stream":true,"input":[]}',
                "more_body": False,
            }

        with tempfile.TemporaryDirectory() as directory:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(upstream)
            ) as client:
                scope = {
                    "type": "http", "method": "POST", "scheme": "http",
                    "path": "/v1/responses", "query_string": b"",
                    "headers": [(b"content-type", b"application/json")],
                    "server": ("offline.invalid", 80),
                    "app": SimpleNamespace(state=SimpleNamespace(
                        upstream="http://offline.invalid", client=client,
                        emulate_stream=True, temperature=None,
                    )),
                }
                stderr = io.StringIO()
                with (
                    mock.patch.dict(
                        os.environ,
                        {"SABER_RESPONSES_STREAM_CAPTURE_DIR": directory},
                    ),
                    contextlib.redirect_stderr(stderr),
                ):
                    response = await PROXY.forward(Request(scope, receive))
                    body = b"".join(
                        [part async for part in response.body_iterator]
                    )

            records = [json.loads(line) for line in stderr.getvalue().splitlines()]
            upstream_record, delivery_record = records
            expected_request_sha = hashlib.sha256(sent_bodies[0]).hexdigest()
            expected_upstream_sha = hashlib.sha256(upstream_body).hexdigest()
            self.assertEqual(upstream_record["phase"], "upstream_complete")
            self.assertEqual(upstream_record["request_sha256"], expected_request_sha)
            self.assertEqual(upstream_record["upstream_body_sha256"], expected_upstream_sha)
            self.assertEqual(upstream_record["upstream_status"], 200)
            self.assertEqual(upstream_record["output_types"], ["message"])
            self.assertEqual(delivery_record["phase"], "delivery_final")
            self.assertTrue(delivery_record["terminal_yielded"])
            capture = json.loads(Path(upstream_record["capture_path"]).read_text())
            self.assertEqual(capture["request_body_utf8"].encode(), sent_bodies[0])
            self.assertEqual(capture["upstream_body_utf8"].encode(), upstream_body)
            self.assertIn(b"event: response.completed", body)

    async def test_wrapper_preserves_bytes_order_and_logs_terminal(self):
        response = completed_response()
        expected = [part async for part in PROXY._emulate_responses_stream(response)]
        diagnostic = {
            "request_sha256": "request-sha", "upstream_body_sha256": "upstream-sha",
            "upstream_status": 200, "response_status": "completed",
            "output_types": ["message"], "completed_result": True, "capture_path": None,
        }
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            actual = [part async for part in PROXY._diagnosed_emulate_responses_stream(response, diagnostic)]
        self.assertEqual(actual, expected)
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["yielded_event_count"], len(expected))
        self.assertEqual(record["last_yielded_event"], "response.completed")
        self.assertTrue(record["terminal_yielded"])
        self.assertEqual(record["outcome"], "completed")

    async def test_early_close_logs_cancellation_without_terminal(self):
        stream = PROXY._diagnosed_emulate_responses_stream(
            completed_response(), {"request_sha256": "request-sha"}
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            first = await anext(stream)
            await stream.aclose()
        self.assertTrue(first.startswith(b"event: response.created"))
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["yielded_event_count"], 1)
        self.assertEqual(record["last_yielded_event"], "response.created")
        self.assertFalse(record["terminal_yielded"])
        self.assertEqual(record["outcome"], "cancelled")
        self.assertEqual(record["failure"], "GeneratorExit")

    async def test_generator_exception_is_logged_and_propagated(self):
        async def broken(_response):
            yield b"event: response.created\ndata: {}\n\n"
            raise RuntimeError("synthetic failure")

        stderr = io.StringIO()
        with mock.patch.object(PROXY, "_emulate_responses_stream", broken):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                    _ = [part async for part in PROXY._diagnosed_emulate_responses_stream({}, {})]
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["outcome"], "exception")
        self.assertEqual(record["failure"], "RuntimeError")
        self.assertFalse(record["terminal_yielded"])

    def test_capture_is_unique_mode_0600_and_exact(self):
        request = b'{"stream":false,"input":[{"role":"user","content":"secret"}]}'
        upstream = json.dumps(completed_response(), separators=(",", ":")).encode()
        request_sha = hashlib.sha256(request).hexdigest()
        upstream_sha = hashlib.sha256(upstream).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"SABER_RESPONSES_STREAM_CAPTURE_DIR": directory}):
                first = PROXY._capture_emulated_exchange(request, upstream, request_sha, upstream_sha)
                second = PROXY._capture_emulated_exchange(request, upstream, request_sha, upstream_sha)
            self.assertNotEqual(first, second)
            for name in (first, second):
                path = Path(name)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                capture = json.loads(path.read_text())
                self.assertEqual(capture["request_body_utf8"].encode(), request)
                self.assertEqual(capture["upstream_body_utf8"].encode(), upstream)
                self.assertEqual(capture["request_sha256"], request_sha)
                self.assertEqual(capture["upstream_body_sha256"], upstream_sha)

    def test_capture_byte_limit_fails_open_without_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.dict(os.environ, {"SABER_RESPONSES_STREAM_CAPTURE_DIR": directory}),
                mock.patch.object(PROXY, "STREAM_CAPTURE_MAX_BYTES", 1),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = PROXY._capture_emulated_exchange(
                    b"{}", b"{}", "request-sha", "upstream-sha"
                )
            self.assertIsNone(result)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
