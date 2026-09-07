"""Offline byte-boundary and partial-stream failure regression."""
import contextlib
import base64
import os
import tempfile
from unittest.mock import patch
import importlib.util
import io
import json
from pathlib import Path
import unittest
import httpx

PATH = Path(__file__).resolve().parents[2] / 'bin/vllm_responses_compat_proxy_gptoss.py'
CAPTURE = (Path(__file__).resolve().parents[2]
           / 'reports/v10-fixes-20260906/gptoss-failure-diagnostic-r1'
           / 'stream-captures/92343a1c658a4c1f8926a70387c43c9f.json')
SPEC = importlib.util.spec_from_file_location('gptoss_stream_test', PATH)
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)


def event(kind, **fields):
    return ('data: ' + json.dumps({'type': kind, **fields}, ensure_ascii=False) + '\n\n').encode()


class Reply:
    def __init__(self, chunks, failure=None):
        self.chunks = chunks
        self.failure = failure
        self.closed = False
        self.reads = 0

    async def aiter_raw(self):
        self.reads += 1
        for chunk in self.chunks:
            yield chunk
        if self.failure:
            raise self.failure

    async def aclose(self):
        self.closed = True


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, reply):
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            data = b''.join([chunk async for chunk in PROXY._forward_responses_stream(reply)])
        self.assertTrue(reply.closed)
        self.assertEqual(reply.reads, 1)
        return data, json.loads(log.getvalue())

    async def test_multibyte_every_byte_boundary_is_exact_passthrough(self):
        wire = event('response.output_text.delta', delta='中文🙂') + event('response.completed', response={'status': 'completed'})
        output, report = await self.collect(Reply([wire[i:i+1] for i in range(len(wire))]))
        self.assertEqual(output, wire)
        self.assertEqual(report['replacement_characters'], 0)
        self.assertIsNone(report['failure'])

    async def test_completed_event_with_incomplete_status_is_normalized(self):
        wire = event('response.completed', response={
            'id': 'resp_incomplete', 'status': 'incomplete', 'output': [],
            'incomplete_details': {'reason': 'max_output_tokens'}})
        output, report = await self.collect(
            Reply([wire[i:i+1] for i in range(len(wire))]))
        self.assertIn(b'"type": "response.incomplete"', output)
        self.assertNotIn(b'"type": "response.completed"', output)
        self.assertEqual(report['terminal_event'], 'response.completed')
        self.assertEqual(report['downstream_rewrite']['rewrites'], [{
            'upstream_event': 'response.completed',
            'upstream_status': 'incomplete',
            'downstream_event': 'response.incomplete',
        }])

    async def test_supported_failed_status_and_crlf_event_field_are_normalized(self):
        payload = json.dumps({'type': 'response.completed',
                              'response': {'status': 'failed'}}, ensure_ascii=False)
        wire = f'event: response.completed\r\ndata: {payload}\r\n\r\n'.encode()
        output, report = await self.collect(Reply([wire[:7], wire[7:]]))
        self.assertTrue(output.startswith(b'event: response.failed\r\n'))
        self.assertIn(b'"type": "response.failed"', output)
        self.assertEqual(report['downstream_rewrite']['rewrite_count'], 1)

    async def test_unsupported_cancelled_status_becomes_explicit_error(self):
        wire = event('response.completed', response={'status': 'cancelled'})
        output, report = await self.collect(Reply([wire]))
        self.assertIn(b'"type": "error"', output)
        self.assertIn(b'unsupported_upstream_terminal_status', output)
        self.assertNotIn(b'response.cancelled', output)
        self.assertEqual(report['downstream_rewrite']['rewrites'][0]
                         ['downstream_event'], 'error')

    async def test_malformed_non_string_status_becomes_explicit_error(self):
        for status in ({'bad': True}, ['incomplete']):
            with self.subTest(status=status):
                wire = event('response.completed', response={'status': status})
                output, report = await self.collect(Reply([wire]))
                self.assertIn(b'unsupported_upstream_terminal_status', output)
                self.assertEqual(report['downstream_rewrite']['rewrite_count'], 1)

    async def test_real_empty_final_capture_replays_as_incomplete(self):
        evidence = json.loads(CAPTURE.read_text())
        upstream = base64.b64decode(evidence['upstream_sse_base64'])
        output, report = await self.collect(
            Reply([upstream[i:i+1] for i in range(len(upstream))]))
        self.assertEqual(base64.b64decode(evidence['upstream_sse_base64']), upstream)
        self.assertIn(b'"type": "response.incomplete"', output)
        self.assertNotEqual(output, upstream)
        self.assertEqual(report['terminal_response']['status'], 'incomplete')
        self.assertEqual(report['downstream_rewrite']['rewrite_count'], 1)

    async def test_reasoning_only_completion_is_reported_without_inventing_text(self):
        response = {"id": "resp_empty", "status": "completed", "output": [
            {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "private"}]}],
            "usage": {"output_tokens": 17}}
        wire = event("response.completed", response=response)
        output, report = await self.collect(Reply([wire]))
        self.assertEqual(output, wire)
        self.assertEqual(report["output_text_delta_chars"], 0)
        self.assertEqual(report["terminal_response"]["output_items"][0]["output_text_chars"], 0)
        self.assertNotIn("private", json.dumps(report))
        self.assertEqual(report["event_counts"], {"response.completed": 1})

    async def test_terminal_text_and_deltas_are_observed_separately(self):
        response = {"status": "completed", "output": [{"type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": "中文🙂"}]}]}
        wire = event("response.output_text.delta", delta="中文🙂") + event("response.completed", response=response)
        output, report = await self.collect(Reply([wire[i:i+1] for i in range(len(wire))]))
        self.assertEqual(output, wire)
        self.assertEqual(report["output_text_delta_chars"], 3)
        self.assertEqual(report["terminal_response"]["output_items"][0]["output_text_chars"], 3)

    async def test_opt_in_capture_preserves_wire_and_excludes_headers(self):
        wire = event("response.completed", response={"status": "completed", "output": []})
        request = b'{"model":"test","input":"hello"}'
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SABER_RESPONSES_STREAM_CAPTURE_DIR": directory}):
                log = io.StringIO()
                with contextlib.redirect_stderr(log):
                    output = b"".join([chunk async for chunk in PROXY._forward_responses_stream(Reply([wire]), request)])
            report = json.loads(log.getvalue())
            path = Path(report["capture_path"])
            evidence = json.loads(path.read_text())
            self.assertEqual(output, wire)
            self.assertEqual(base64.b64decode(evidence["upstream_sse_base64"]), wire)
            self.assertEqual(base64.b64decode(evidence["request_base64"]), request)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(evidence["stream_truncated"])
            self.assertNotIn("headers", evidence)

    async def test_partial_tool_stream_is_retained_without_retry_or_success(self):
        partial = event('response.function_call_arguments.delta', delta='{"command":')
        for failure in (None, httpx.RemoteProtocolError('incomplete chunked read')):
            with self.subTest(failure=failure):
                output, report = await self.collect(Reply([partial], failure))
                self.assertTrue(output.startswith(partial))
                self.assertIn(b'upstream_stream_incomplete', output)
                self.assertNotIn(b'response.completed', output)
                self.assertIsNotNone(report['failure'])

    async def test_partial_frame_is_forwarded_before_error(self):
        complete = event('response.function_call_arguments.delta', delta='first')
        partial = b'data: {"type":"response.function_call_arguments.delta","delta":"second'
        output, report = await self.collect(Reply([complete + partial]))
        self.assertTrue(output.startswith(complete + partial))
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertEqual(report['failure'], 'ValueError')

    async def test_frame_buffer_bound_fails_without_dropping_partial_bytes(self):
        partial = b'x' * 65
        with patch.object(PROXY.ResponsesTerminalRewriter, 'MAX_FRAME_BYTES', 64):
            output, report = await self.collect(Reply([partial]))
        self.assertTrue(output.startswith(partial))
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertEqual(report['failure'], 'ValueError')

    async def test_complete_tool_frame_preceding_oversized_partial_is_retained(self):
        complete = event('response.function_call_arguments.delta', delta='kept')
        partial = b'x' * 65
        with patch.object(PROXY.ResponsesTerminalRewriter, 'MAX_FRAME_BYTES', 64):
            output, report = await self.collect(Reply([complete + partial]))
        self.assertTrue(output.startswith(complete + partial))
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertEqual(report['failure'], 'ValueError')

    async def test_oversized_complete_frame_is_forwarded_before_error(self):
        complete = event('response.function_call_arguments.delta', delta='x' * 80)
        with patch.object(PROXY.ResponsesTerminalRewriter, 'MAX_FRAME_BYTES', 64):
            output, report = await self.collect(Reply([complete]))
        self.assertTrue(output.startswith(complete))
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertEqual(report['failure'], 'ValueError')

    async def test_rewrite_preserves_crlf_frame_envelope(self):
        payload = json.dumps({'type': 'response.completed',
                              'response': {'status': 'incomplete'}}, separators=(',', ':'))
        wire = ('event: response.completed\r\n'
                'id: terminal-1\r\n'
                f'data: {payload}\r\n\r\n').encode()
        output, _ = await self.collect(Reply([wire]))
        self.assertTrue(output.startswith(b'event: response.incomplete\r\n'
                                          b'id: terminal-1\r\n'))
        self.assertTrue(output.endswith(b'\r\n\r\n'))
        self.assertFalse(output.endswith(b'\r\n\r\n\r\n'))

    async def test_failed_and_incomplete_terminal_are_preserved(self):
        for kind in ('response.failed', 'response.incomplete', 'error'):
            wire = event(kind)
            output, report = await self.collect(Reply([wire]))
            self.assertEqual(output, wire)
            self.assertEqual(report['terminal_event'], kind)

    async def test_done_sentinel_alone_does_not_invent_success(self):
        output, report = await self.collect(Reply([b'data: [DONE]\n\n']))
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertIsNone(report['terminal_event'])

    async def test_invalid_utf8_is_not_silently_replaced(self):
        output, report = await self.collect(Reply([b'data: {"type":"delta","text":"\xff"}\n\n']))
        self.assertEqual(report['failure'], 'UnicodeDecodeError')
        self.assertIn(b'upstream_stream_incomplete', output)
        self.assertNotIn('\ufffd'.encode(), output)


if __name__ == '__main__':
    unittest.main()
