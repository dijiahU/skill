"""Opt-in v10 middleware: count the exact Responses rendering without generation.

Install in a NEW service with --middleware
saber_vllm_token_count.TokenCountMiddleware and this directory on PYTHONPATH.
No installed vLLM files are modified. Unsupported versions fail explicitly.
"""
from __future__ import annotations

import hashlib
import json
import sys

PROTOCOL = 'saber-responses-budget-v1'


async def count_response_tokens(handler, payload, request_type):
    if not isinstance(payload, dict):
        raise ValueError('Responses token-count input must be an object')
    if payload.get('previous_response_id'):
        raise ValueError('Token-count requires explicit complete input history')
    if payload.get('truncation', 'disabled') != 'disabled':
        raise ValueError('Token-count does not permit silent input truncation')
    adapted = dict(payload)
    # Render only. A minimal reserve avoids rejecting an otherwise renderable
    # prompt due to the caller output budget before its token count is known.
    adapted.update(max_output_tokens=1, stream=False, background=False, store=False)
    request = request_type.model_validate(adapted)
    check = await handler._check_model(request)
    if check is not None:
        raise ValueError('Requested model is unavailable for token counting')
    if handler.use_harmony:
        _, prompts = handler._make_request_with_harmony(request, None)
        renderer = 'responses_harmony'
    else:
        _, prompts = await handler._make_request(request, None)
        renderer = 'responses_chat'
    if len(prompts) != 1:
        raise ValueError('Expected exactly one Responses engine prompt')
    count = handler._extract_prompt_len(prompts[0])
    context = handler.model_config.max_model_len
    if type(count) is not int or type(context) is not int or count < 0 or context <= 0:
        raise ValueError('Invalid token count or context limit from service')
    return {
        'protocol': PROTOCOL, 'input_tokens': count, 'context_limit': context,
        'renderer': renderer,
        'compatibility': {
            'mistral_utf8': getattr(sys.modules.get('vllm.tokenizers.detokenizer_utils'), '_saber_mistral_utf8_patch', None),
            'engine_mistral_utf8': getattr(sys.modules.get('vllm.v1.engine.detokenizer'), '_saber_mistral_utf8_patch', None),
        },
        'request_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
    }


async def token_count_endpoint(request):
    from starlette.responses import JSONResponse
    try:
        from vllm.entrypoints.openai.responses.protocol import ResponsesRequest
        handler = request.app.state.openai_serving_responses
        result = await count_response_tokens(handler, await request.json(), ResponsesRequest)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({'error': {'code': 'responses_token_count_failed', 'type': type(exc).__name__, 'message': str(exc)}}, status_code=400)


class TokenCountMiddleware:
    def __init__(self, app):
        self.app = app
        self.registered = False

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and not self.registered:
            from starlette.routing import Route
            # Register on the router, then pass through ALL inner middleware,
            # including vLLM API authentication. Never answer outside that chain.
            scope['app'].router.routes.append(Route(
                '/v1/saber/responses/token-count', token_count_endpoint, methods=['POST']))
            self.registered = True
        await self.app(scope, receive, send)
