import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

PATH = Path(__file__).resolve().parents[2] / 'bin/saber_vllm_token_count.py'
SPEC = importlib.util.spec_from_file_location('token_count_test', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TokenCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_server_renderer_for_chat_and_harmony_without_generation(self):
        for harmony in (False, True):
            with self.subTest(harmony=harmony):
                rendered = [dict(prompt_token_ids=[1, 2, 3])]
                handler = SimpleNamespace(
                    use_harmony=harmony, model_config=SimpleNamespace(max_model_len=32768),
                    _check_model=AsyncMock(return_value=None),
                    _make_request=AsyncMock(return_value=([], rendered)),
                    _make_request_with_harmony=Mock(return_value=([], rendered)),
                    _extract_prompt_len=lambda p: len(p['prompt_token_ids']),
                )
                schema = SimpleNamespace(model_validate=Mock(side_effect=lambda p: SimpleNamespace(**p)))
                payload = {'model': 'test', 'input': '中文🙂', 'max_output_tokens': 4096}
                result = await MODULE.count_response_tokens(handler, payload, schema)
                self.assertEqual(result['input_tokens'], 3)
                self.assertEqual(result['context_limit'], 32768)
                self.assertEqual(payload['max_output_tokens'], 4096)
                adapted = schema.model_validate.call_args.args[0]
                self.assertEqual(adapted['max_output_tokens'], 1)
                self.assertEqual(adapted['input'], payload['input'])
                self.assertFalse(adapted['store'])
                self.assertEqual(handler._make_request.await_count, int(not harmony))
                self.assertEqual(handler._make_request_with_harmony.call_count, int(harmony))

    async def test_no_silent_truncation_or_unresolved_stored_history(self):
        for payload in ({'previous_response_id': 'old'}, {'truncation': 'auto'}, []):
            with self.assertRaises(ValueError):
                await MODULE.count_response_tokens(None, payload, None)

    async def test_custom_endpoint_still_passes_through_inner_authentication(self):
        import httpx
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        class Deny:
            def __init__(self, app): self.app = app
            async def __call__(self, scope, receive, send):
                await JSONResponse({'error': 'unauthorized'}, status_code=401)(scope, receive, send)
        app = Starlette()
        app.add_middleware(Deny)
        app.add_middleware(MODULE.TokenCountMiddleware)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
            result = await client.post('/v1/saber/responses/token-count', json={})
        self.assertEqual(result.status_code, 401)
        self.assertEqual(sum(r.path == '/v1/saber/responses/token-count' for r in app.routes), 1)


if __name__ == '__main__': unittest.main()
