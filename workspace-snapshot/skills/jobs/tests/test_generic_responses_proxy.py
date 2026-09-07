"""Offline compatibility-proxy checks; every upstream reply stays in memory."""

import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import httpx
from starlette.requests import Request


PROXY_PATH = Path(__file__).resolve().parents[2] / "bin/vllm_responses_compat_proxy.py"
SPEC = importlib.util.spec_from_file_location("generic_proxy_under_test", PROXY_PATH)
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)


class MemoryBody(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content
        self.closed = False

    async def __aiter__(self):
        yield self.content

    async def aclose(self):
        self.closed = True


class GenericResponsesProxyTests(unittest.IsolatedAsyncioTestCase):
    async def forward(self, status, payload=None, *, raw=None, headers=None, request=None):
        upstream_body = raw if raw is not None else json.dumps(payload).encode()
        stream = MemoryBody(upstream_body)
        captured = []

        async def upstream(upstream_request):
            captured.append(json.loads(upstream_request.content))
            return httpx.Response(
                status,
                headers=headers or {"content-type": "application/json"},
                stream=stream,
            )

        request_payload = request if request is not None else {"stream": True, "input": []}

        async def receive():
            return {
                "type": "http.request",
                "body": json.dumps(request_payload).encode(),
                "more_body": False,
            }

        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            scope = {
                "type": "http",
                "method": "POST",
                "scheme": "http",
                "path": "/v1/responses",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "server": ("offline.invalid", 80),
                "app": SimpleNamespace(
                    state=SimpleNamespace(upstream="http://offline.invalid", client=client, emulate_stream=True, temperature=None)
                ),
            }
            with contextlib.redirect_stderr(io.StringIO()):
                response = await PROXY.forward(Request(scope, receive))
            if hasattr(response, "body_iterator"):
                body = b"".join([part async for part in response.body_iterator])
            else:
                body = response.body
        self.assertTrue(stream.closed)
        self.assertEqual(len(captured), 1, "the proxy must not retry upstream requests")
        return response, body, captured[0]

    @staticmethod
    def completed():
        return {
            "object": "response",
            "id": "resp_offline",
            "status": "completed",
            "error": None,
            "output": [],
            "usage": {"input_tokens": 17, "output_tokens": 4, "total_tokens": 21},
        }

    async def test_completed_stream_bytes_remain_stable(self):
        payload = {
            "object": "response", "id": "resp_bytes", "status": "completed",
            "error": None, "output": [],
            "usage": {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1},
        }
        body = b"".join([part async for part in PROXY._emulate_responses_stream(payload)])
        self.assertEqual(len(body), 632)
        self.assertEqual(
            hashlib.sha256(body).hexdigest(),
            "542768b8d4ff4f42ffbd0221afb7dab6d196ca8fed5dd08abc14f70988334afc",
        )

    async def test_completed_result_replays_the_success_lifecycle(self):
        payload = self.completed()
        payload["output"] = [
            {
                "type": "message",
                "id": "msg_offline",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "ready", "annotations": []}],
            },
            {
                "type": "function_call",
                "id": "fc_offline",
                "call_id": "call_offline",
                "name": "inspect",
                "arguments": '{"mode":"preview"}',
                "status": "completed",
            },
        ]
        response, body, upstream = await self.forward(200, payload)
        events = [json.loads(line[6:]) for line in body.decode().splitlines() if line.startswith("data: ")]
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertEqual(events[0]["type"], "response.created")
        self.assertEqual(events[-1]["type"], "response.completed")
        self.assertEqual(events[-1]["response"], payload)
        self.assertEqual([event["sequence_number"] for event in events], list(range(len(events))))
        self.assertFalse(upstream["stream"])

    async def test_http_errors_preserve_status_json_and_retry_headers(self):
        for status in (400, 401, 429, 500):
            with self.subTest(status=status):
                payload = {"error": {"type": "SyntheticError", "code": status, "message": "offline failure"}}
                response, body, _ = await self.forward(
                    status, payload, headers={"content-type": "application/json", "retry-after": "7"}
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["content-type"], "application/json")
                self.assertEqual(response.headers["retry-after"], "7")
                self.assertEqual(body, json.dumps(payload).encode())
                self.assertNotIn(b"event: response.", body)

    async def test_error_objects_in_http_success_are_not_success_sse(self):
        for payload in (
            {"error": {"message": "offline failure"}},
            {**self.completed(), "error": {"message": "offline failure"}},
        ):
            with self.subTest(payload=payload):
                response, body, _ = await self.forward(200, payload)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(json.loads(body), payload)
                self.assertEqual(response.headers["content-type"], "application/json")

    async def test_failed_and_incomplete_results_emit_exact_terminal_sse(self):
        for status in ("failed", "incomplete"):
            with self.subTest(status=status):
                payload = {**self.completed(), "status": status}
                payload["error"] = {"code": "model_error", "message": "generation stopped"} if status == "failed" else None
                if status == "incomplete":
                    payload["incomplete_details"] = {"reason": "max_output_tokens"}
                payload["output"] = [{"type": "reasoning", "id": "rs_partial", "summary": []}]
                response, body, _ = await self.forward(200, payload)
                events = [json.loads(line[6:]) for line in body.decode().splitlines() if line.startswith("data: ")]
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
                self.assertEqual([event["type"] for event in events], [
                    "response.created", "response.in_progress", f"response.{status}",
                ])
                self.assertEqual(events[-1]["response"], payload)

    async def test_nonterminal_success_objects_are_explicit_protocol_errors(self):
        for status in ("in_progress", "queued", "cancelled"):
            with self.subTest(status=status):
                payload = {**self.completed(), "status": status}
                response, body, _ = await self.forward(200, payload)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(json.loads(body), payload)
                self.assertNotIn(b"event: response.", body)

    async def test_partial_tool_call_is_preserved_but_never_marked_done(self):
        payload = {**self.completed(), "status": "incomplete", "error": None,
                   "incomplete_details": {"reason": "max_output_tokens"},
                   "output": [{"type": "function_call", "id": "fc_partial",
                               "call_id": "call_partial", "name": "apply_patch",
                               "arguments": '{"patch":"unterminated'}]}
        response, body, _ = await self.forward(200, payload)
        events = [json.loads(line[6:]) for line in body.decode().splitlines() if line.startswith("data: ")]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(events[-1]["type"], "response.incomplete")
        self.assertEqual(events[-1]["response"], payload)
        self.assertNotIn("response.function_call_arguments.done", [event["type"] for event in events])
        self.assertNotIn("response.output_item.done", [event["type"] for event in events])
        self.assertNotIn("response.completed", [event["type"] for event in events])

    async def test_unhashable_status_values_are_explicit_protocol_errors(self):
        for status in ([], {}):
            with self.subTest(status=status):
                payload = {**self.completed(), "status": status}
                response, body, _ = await self.forward(200, payload)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(json.loads(body), payload)
                self.assertNotIn(b"event: response.", body)

    async def test_nonresponses_and_malformed_results_are_not_replayed(self):
        for payload in (
            None,
            [],
            {"status": "completed", "output": []},
            {**self.completed(), "output": "not a list"},
            {**self.completed(), "output": [None]},
            {**self.completed(), "output": [{"type": "message", "content": None}]},
            {**self.completed(), "output": [{"type": "function_call", "arguments": {}}]},
            {**self.completed(), "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
             "output": [{"type": "function_call", "arguments": {}}]},
        ):
            with self.subTest(payload=payload):
                response, body, _ = await self.forward(200, payload)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(json.loads(body), payload)

    async def test_nonjson_upstream_body_is_preserved_and_closed(self):
        for status in (200, 502):
            with self.subTest(status=status):
                original = b"<html>offline upstream failure</html>"
                response, body, _ = await self.forward(
                    status, raw=original, headers={"content-type": "text/html"}
                )
                self.assertEqual(response.status_code, 502 if status == 200 else status)
                self.assertEqual(body, original)
                self.assertEqual(response.headers["content-type"], "text/html")

    async def test_decoded_error_body_does_not_keep_compression_header(self):
        original = b'{"error":{"message":"offline failure"}}'
        response, body, _ = await self.forward(
            400,
            raw=gzip.compress(original),
            headers={"content-type": "application/json", "content-encoding": "gzip"},
        )
        self.assertEqual(body, original)
        self.assertNotIn("content-encoding", response.headers)

    async def test_multibyte_text_and_tool_arguments_survive_replay(self):
        original = "中文路径/安全检查🙂é"
        payload = self.completed()
        payload["output"] = [
            {"type": "message", "id": "msg_unicode", "role": "assistant",
             "content": [{"type": "output_text", "text": original}]},
            {"type": "function_call", "id": "fc_unicode", "name": "inspect",
             "call_id": "call_unicode", "arguments": json.dumps({"path": original}, ensure_ascii=False)},
        ]
        _, body, _ = await self.forward(200, payload)
        events = [json.loads(line[6:]) for line in body.decode("utf-8", errors="strict").splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1]["response"], payload)
        self.assertNotIn("\ufffd", body.decode())
        self.assertEqual(next(e["delta"] for e in events if e["type"] == "response.output_text.delta"), original)

    async def test_nonstream_responses_are_still_raw_passthrough(self):
        for status, payload in ((200, self.completed()), (400, {"error": {"message": "offline failure"}})):
            with self.subTest(status=status):
                response, body, _ = await self.forward(
                    status, payload, request={"stream": False, "input": []}
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(json.loads(body), payload)

    async def test_non_success_http_never_replays_even_a_completed_body(self):
        payload = self.completed()
        response, body, _ = await self.forward(400, payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(body), payload)

    async def test_direct_replay_rejects_errors_before_emitting_any_event(self):
        events = []
        with self.assertRaises(ValueError):
            async for event in PROXY._emulate_responses_stream({"error": {"message": "offline"}}):
                events.append(event)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
