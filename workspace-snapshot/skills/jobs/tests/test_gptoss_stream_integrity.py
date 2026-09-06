"""Offline byte-boundary and partial-stream failure regression."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import httpx

PATH = Path(__file__).resolve().parents[2] / 'bin/vllm_responses_compat_proxy_gptoss.py'
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

    async def test_partial_tool_stream_is_retained_without_retry_or_success(self):
        partial = event('response.function_call_arguments.delta', delta='{"command":')
        for failure in (None, httpx.RemoteProtocolError('incomplete chunked read')):
            with self.subTest(failure=failure):
                output, report = await self.collect(Reply([partial], failure))
                self.assertTrue(output.startswith(partial))
                self.assertIn(b'upstream_stream_incomplete', output)
                self.assertNotIn(b'response.completed', output)
                self.assertIsNotNone(report['failure'])

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
