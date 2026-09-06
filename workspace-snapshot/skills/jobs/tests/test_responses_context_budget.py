import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import httpx

BIN = Path(__file__).resolve().parents[2] / 'bin'
sys.path.insert(0, str(BIN))
from saber_responses_budget import apply_budget, guard_request, ContextBudgetError, PROTOCOL


def count(payload, n=28673, context=32768):
    return {'protocol': PROTOCOL, 'input_tokens': n, 'context_limit': context,
            'renderer': 'responses_chat', 'request_sha256': hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}


class BudgetTests(unittest.IsolatedAsyncioTestCase):
    def test_reported_glm_boundary_keeps_full_input_and_reserves_margin(self):
        payload = {'input': '中文🙂' * 100, 'max_output_tokens': 4096, 'instructions': 'retain policy'}
        adapted, report = apply_budget(payload, count(payload))
        self.assertEqual(adapted['input'], payload['input'])
        self.assertEqual(adapted['instructions'], payload['instructions'])
        self.assertEqual(adapted['max_output_tokens'], 3967)
        self.assertEqual(report['input_tokens'] + report['allocated_output_tokens'] + report['margin'], 32768)
        self.assertEqual(payload['max_output_tokens'], 4096)

    def test_small_requests_not_expanded_or_silently_truncated(self):
        payload = {'max_output_tokens': 64, 'input': 'x'}
        adapted, _ = apply_budget(payload, count(payload, n=20))
        self.assertEqual(adapted['max_output_tokens'], 64)
        with self.assertRaises(ContextBudgetError):
            apply_budget(payload, count(payload, n=32700))

    def test_stale_count_protocol_and_invalid_numbers_rejected(self):
        payload = {'input': 'new'}
        for record in (count({'input': 'old'}), {**count(payload), 'protocol': 'old'},
                       {**count(payload), 'input_tokens': True}, {**count(payload), 'context_limit': -1}):
            with self.assertRaises(ContextBudgetError):
                apply_budget(payload, record)

    async def test_guard_uses_exact_payload_without_generation(self):
        payload = {'input': '中文', 'max_output_tokens': 4096}
        calls = []
        async def handler(request):
            calls.append(request)
            self.assertEqual(request.url.path, '/v1/saber/responses/token-count')
            self.assertEqual(json.loads(request.content), payload)
            return httpx.Response(200, json=count(payload))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            body, report = await guard_request(client, 'http://offline', json.dumps(payload).encode(), {})
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(body)['max_output_tokens'], 3967)

    async def test_each_proxy_requires_count_before_generation(self):
        from types import SimpleNamespace
        from starlette.requests import Request
        for name in ('vllm_responses_compat_proxy', 'vllm_responses_compat_proxy_glm47', 'vllm_responses_compat_proxy_gptoss'):
            with self.subTest(proxy=name):
                spec = importlib.util.spec_from_file_location(name + '_budget', BIN / (name + '.py'))
                proxy = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(proxy)
                paths = []
                async def upstream(request):
                    paths.append(request.url.path)
                    return httpx.Response(503, json={'error': 'offline unavailable'})
                async def receive():
                    return {'type': 'http.request', 'body': b'{"input":[],"stream":true}', 'more_body': False}
                async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                    scope = {'type': 'http', 'method': 'POST', 'path': '/v1/responses', 'query_string': b'',
                             'scheme': 'http', 'headers': [], 'server': ('offline', 80),
                             'app': SimpleNamespace(state=SimpleNamespace(client=client, upstream='http://offline', temperature=None, emulate_stream=True))}
                    with patch.dict('os.environ', {'SABER_RESPONSES_CONTEXT_GUARD': '1'}):
                        response = await proxy.forward(Request(scope, receive))
                self.assertEqual(paths, ['/v1/saber/responses/token-count'])
                self.assertEqual(response.status_code, 503)
                self.assertIn(b'token_count_unavailable', response.body)


if __name__ == '__main__': unittest.main()
