import hashlib
import importlib.util
import json
from itertools import product
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
    async def test_unsupported_tool_history_preserves_rejection(self):
        from saber_responses_budget import normalize_rejected_tool_history
        call = {'type': 'function_call', 'call_id': 'call_unsupported',
                'name': 'apply_patch', 'arguments': '{"command": "unterminated'}
        output = {'type': 'function_call_output', 'call_id': 'call_unsupported',
                  'output': 'unsupported call: apply_patch'}
        payload = {'input': [call, output], 'max_output_tokens': 512}
        normalized = normalize_rejected_tool_history(payload)
        wrapped = json.loads(normalized['input'][0]['arguments'])['__saber_rejected_argument_history__']
        self.assertEqual(wrapped['raw_arguments'], call['arguments'])
        self.assertEqual(wrapped['rejection_kind'], 'unsupported_tool')
        self.assertFalse(wrapped['executed'])
        self.assertEqual(normalized['input'][1], output)
        self.assertEqual(payload['input'], [call, output])
        self.assertEqual(normalize_rejected_tool_history(normalized), normalized)
        async def handler(request):
            self.assertEqual(json.loads(request.content), normalized)
            return httpx.Response(200, json=count(normalized, n=100))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            body, _ = await guard_request(client, 'http://offline', json.dumps(payload).encode(), {})
        self.assertEqual(json.loads(body), normalized)
        for items in ([call], [output, call], [call, output, output],
                      [{**call, 'name': 'saber_bash'}, output],
                      [call, {**output, 'output': output['output'] + ' extra'}],
                      [{**call, 'arguments': '{"command": "true"}'}, output]):
            untouched = {'input': items}
            self.assertEqual(normalize_rejected_tool_history(untouched), untouched)

    async def test_unavailable_native_tool_history_preserves_rejection(self):
        from copy import deepcopy
        from saber_responses_budget import normalize_rejected_tool_history
        call = {'type': 'function_call', 'call_id': 'call_unavailable',
                'name': 'request_user_input', 'arguments': '{"questions": ['}
        output = {'type': 'function_call_output', 'call_id': 'call_unavailable',
                  'output': 'request_user_input is unavailable in Default mode'}
        payload = {'input': [call, output], 'max_output_tokens': 512}
        original = deepcopy(payload)
        normalized = normalize_rejected_tool_history(payload)
        wrapped = json.loads(normalized['input'][0]['arguments'])['__saber_rejected_argument_history__']
        self.assertEqual(wrapped['raw_arguments'], call['arguments'])
        self.assertEqual(wrapped['rejection_kind'], 'tool_unavailable')
        self.assertFalse(wrapped['executed'])
        self.assertEqual(normalized['input'][1], output)
        self.assertEqual(payload, original)
        self.assertEqual(normalize_rejected_tool_history(normalized), normalized)
        async def handler(request):
            self.assertEqual(json.loads(request.content), normalized)
            return httpx.Response(200, json=count(normalized, n=100))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            body, _ = await guard_request(client, 'http://offline', json.dumps(payload).encode(), {})
        self.assertEqual(json.loads(body), normalized)
        for items in ([call], [output, call], [call, output, output],
                      [{**call, 'name': 'saber_bash'}, output],
                      [call, {**output, 'output': output['output'] + ' extra'}],
                      [{**call, 'arguments': '{"questions": []}'}, output]):
            untouched = {'input': items}
            self.assertEqual(normalize_rejected_tool_history(untouched), untouched)

    async def test_rejected_history_is_counted_and_returned_identically(self):
        from copy import deepcopy
        from saber_responses_budget import normalize_rejected_tool_history
        raw = '{"command":"unterminated'
        call = {'type': 'function_call', 'call_id': 'call_test', 'name': 'saber_bash', 'arguments': raw}
        output = {'type': 'function_call_output', 'call_id': 'call_test',
                  'output': 'failed to parse function arguments: EOF while parsing a string'}
        payload = {'input': [call, output], 'max_output_tokens': 512}
        original = deepcopy(payload)
        normalized = normalize_rejected_tool_history(payload)
        wrapped = json.loads(normalized['input'][0]['arguments'])['__saber_rejected_argument_history__']
        self.assertEqual(wrapped['raw_arguments'], raw)
        self.assertEqual(wrapped['raw_arguments_sha256'], hashlib.sha256(raw.encode()).hexdigest())
        self.assertFalse(wrapped['executed'])
        self.assertEqual(normalized['input'][1], output)
        self.assertEqual(payload, original)
        self.assertEqual(normalize_rejected_tool_history(normalized), normalized)
        async def handler(request):
            self.assertEqual(json.loads(request.content), normalized)
            return httpx.Response(200, json=count(normalized, n=100))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            body, metadata = await guard_request(client, 'http://offline', json.dumps(payload).encode(), {})
        self.assertEqual(json.loads(body), normalized)
        self.assertEqual(metadata['request_sha256'], count(normalized)['request_sha256'])
        for untouched in (
            {'input': [call]},
            {'input': [call, {**output, 'output': 'command executed'}]},
            {'input': [call, output, output]},
            {'input': [output, call]},
            {'input': [{**call, 'arguments': '{"command":"true"}'}, output]},
        ):
            self.assertEqual(normalize_rejected_tool_history(untouched), untouched)

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

    async def test_input_rejection_keeps_diagnostic_and_request_binding(self):
        from saber_responses_budget import TokenCountRequestError
        payload = {'input': 'unchanged history'}
        calls = []
        async def handler(request):
            calls.append(request.url.path)
            return httpx.Response(400, json={'error': {'message': 'invalid assistant sequence'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(TokenCountRequestError) as caught:
                await guard_request(client, 'http://offline', json.dumps(payload).encode(), {})
        error = caught.exception
        self.assertEqual(error.upstream_status, 400)
        self.assertEqual(error.request_sha256, count(payload)['request_sha256'])
        self.assertIn('invalid assistant sequence', str(error))
        self.assertEqual(calls, ['/v1/saber/responses/token-count'])

    async def test_each_proxy_requires_count_before_generation(self):
        from types import SimpleNamespace
        from starlette.requests import Request
        for name, upstream_status in product(
            ('vllm_responses_compat_proxy', 'vllm_responses_compat_proxy_glm47', 'vllm_responses_compat_proxy_gptoss'),
            (400, 422, 503),
        ):
            with self.subTest(proxy=name, upstream_status=upstream_status):
                spec = importlib.util.spec_from_file_location(name + '_budget', BIN / (name + '.py'))
                proxy = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(proxy)
                paths = []
                async def upstream(request):
                    paths.append(request.url.path)
                    return httpx.Response(upstream_status, json={'error': 'original counting diagnostic'})
                async def receive():
                    return {'type': 'http.request', 'body': b'{"input":[],"stream":true}', 'more_body': False}
                async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                    scope = {'type': 'http', 'method': 'POST', 'path': '/v1/responses', 'query_string': b'',
                             'scheme': 'http', 'headers': [], 'server': ('offline', 80),
                             'app': SimpleNamespace(state=SimpleNamespace(client=client, upstream='http://offline', temperature=None, emulate_stream=True))}
                    with patch.dict('os.environ', {'SABER_RESPONSES_CONTEXT_GUARD': '1'}):
                        response = await proxy.forward(Request(scope, receive))
                self.assertEqual(paths, ['/v1/saber/responses/token-count'])
                rejected = upstream_status in (400, 422)
                self.assertEqual(response.status_code, 400 if rejected else 503)
                self.assertIn(b'token_count_request_rejected' if rejected else b'token_count_unavailable', response.body)
                if rejected:
                    self.assertIn(b'original counting diagnostic', response.body)


if __name__ == '__main__': unittest.main()
