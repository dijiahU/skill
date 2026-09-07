import importlib.util
import contextlib
import io
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


    async def test_post_start_harmony_error_becomes_explicit_error_terminal(self):
        HarmonyError = type('HarmonyError', (Exception,), {'__module__': 'openai_harmony'})

        async def broken(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'text/event-stream')]})
            await send({'type': 'http.response.body',
                        'body': (b'event: response.function_call_arguments.delta\n'
                                 b'data: {"type":"response.function_call_arguments.delta",'
                                 b'"delta":"{\\"command\\":""}\n\n'),
                        'more_body': True})
            raise HarmonyError('synthetic bad token boundary')

        sent = []
        async def collect(message): sent.append(message)
        middleware = MODULE.TokenCountMiddleware(broken)
        scope = {'type': 'http', 'path': '/v1/responses',
                 'app': SimpleNamespace(router=SimpleNamespace(routes=[]))}
        with contextlib.redirect_stderr(io.StringIO()) as evidence:
            await middleware(scope, None, collect)
        body = b''.join(message.get('body', b'') for message in sent)
        partial = (b'event: response.function_call_arguments.delta\n'
                   b'data: {"type":"response.function_call_arguments.delta",'
                   b'"delta":"{\\"command\\":""}\n\n')
        self.assertTrue(body.startswith(partial))
        self.assertEqual(body[:len(partial)], partial)
        self.assertIn(b'event: error', body)
        self.assertIn(b'harmony_stream_parse_failed', body)
        self.assertNotIn(b'response.completed', body)
        self.assertNotIn(b'response.function_call_arguments.done', body)
        self.assertNotIn(b'response.output_item.done', body)
        self.assertFalse(sent[-1]['more_body'])
        self.assertIn('synthetic bad token boundary', evidence.getvalue())

    async def test_negative_harmony_boundaries_are_not_caught(self):
        HarmonyError = type('HarmonyError', (Exception,), {'__module__': 'openai_harmony'})
        OtherError = type('HarmonyError', (Exception,), {'__module__': 'other_parser'})

        cases = [
            ('non_harmony', '/v1/responses', b'text/event-stream', OtherError('other')),
            ('wrong_endpoint', '/v1/chat/completions', b'text/event-stream', HarmonyError('path')),
            ('non_sse', '/v1/responses', b'application/json', HarmonyError('content type')),
        ]
        for name, path, content_type, failure in cases:
            with self.subTest(name=name):
                async def broken(scope, receive, send):
                    await send({'type': 'http.response.start', 'status': 200,
                                'headers': [(b'content-type', content_type)]})
                    raise failure
                async def collect(_message): pass
                middleware = MODULE.TokenCountMiddleware(broken)
                scope = {'type': 'http', 'path': path,
                         'app': SimpleNamespace(router=SimpleNamespace(routes=[]))}
                with self.assertRaises(type(failure)):
                    await middleware(scope, None, collect)

    async def test_harmony_error_after_closed_body_is_not_caught(self):
        HarmonyError = type('HarmonyError', (Exception,), {'__module__': 'openai_harmony'})
        async def broken(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'text/event-stream')]})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
            raise HarmonyError('after close')
        async def collect(_message): pass
        middleware = MODULE.TokenCountMiddleware(broken)
        scope = {'type': 'http', 'path': '/v1/responses',
                 'app': SimpleNamespace(router=SimpleNamespace(routes=[]))}
        with self.assertRaises(HarmonyError):
            await middleware(scope, None, collect)

    async def test_starlette_streaming_response_collapses_single_harmony_error(self):
        import httpx
        from starlette.applications import Starlette
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
        HarmonyError = type('HarmonyError', (Exception,), {'__module__': 'openai_harmony'})
        partial = b'event: response.created\ndata: {}\n\n'
        async def stream():
            yield partial
            raise HarmonyError('synthetic streaming generator failure')
        async def endpoint(_request):
            return StreamingResponse(stream(), media_type='text/event-stream')
        app = Starlette(routes=[Route('/v1/responses', endpoint, methods=['POST'])])
        app.add_middleware(MODULE.TokenCountMiddleware)
        with contextlib.redirect_stderr(io.StringIO()) as evidence:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                          base_url='http://offline') as client:
                response = await client.post('/v1/responses')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(partial))
        self.assertIn(b'harmony_stream_parse_failed', response.content)
        self.assertNotIn(b'response.completed', response.content)
        self.assertIn('synthetic streaming generator failure', evidence.getvalue())

    async def test_harmony_error_is_not_caught_before_sse_start(self):
        HarmonyError = type('HarmonyError', (Exception,), {'__module__': 'openai_harmony'})

        async def broken(_scope, _receive, _send):
            raise HarmonyError('pre-start')

        middleware = MODULE.TokenCountMiddleware(broken)
        scope = {'type': 'http', 'path': '/v1/responses',
                 'app': SimpleNamespace(router=SimpleNamespace(routes=[]))}
        with self.assertRaises(HarmonyError):
            await middleware(scope, None, AsyncMock())


if __name__ == '__main__': unittest.main()
