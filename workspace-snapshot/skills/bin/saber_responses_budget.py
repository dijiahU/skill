"""Versioned exact-render budget guard, enabled only for new SABER services."""
from __future__ import annotations
import hashlib
import json

PROTOCOL = 'saber-responses-budget-v1'


class ContextBudgetError(ValueError):
    pass


def apply_budget(payload, counted, *, output_default=4096, margin=128):
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    if counted.get('protocol') != PROTOCOL or counted.get('request_sha256') != expected:
        raise ContextBudgetError('Token count is not bound to this exact request and protocol')
    input_tokens, context = counted.get('input_tokens'), counted.get('context_limit')
    requested = payload.get('max_output_tokens', output_default)
    if requested is None:
        requested = output_default
    if any(type(v) is not int for v in (input_tokens, context, requested, margin)):
        raise ContextBudgetError('Budget fields must be integers')
    if input_tokens < 0 or context <= 0 or requested <= 0 or margin < 1:
        raise ContextBudgetError('Invalid context budget values')
    available = context - input_tokens - margin
    minimum = min(256, requested)
    if available < minimum:
        raise ContextBudgetError(f'Context cannot fit a useful response: input={input_tokens}, context={context}, margin={margin}, minimum_output={minimum}')
    output = min(requested, available)
    adapted = dict(payload)
    adapted['max_output_tokens'] = output
    return adapted, {
        'protocol': PROTOCOL, 'request_sha256': expected,
        'input_tokens': input_tokens, 'context_limit': context, 'margin': margin,
        'requested_output_tokens': requested, 'allocated_output_tokens': output,
        'renderer': counted.get('renderer'), 'adjusted': output != requested,
    }


async def guard_request(client, upstream, body, headers):
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ContextBudgetError('Responses request must be an object')
    # Same adapted body is counted and subsequently submitted. No hidden history
    # truncation, extra tool execution, or generation request is used to count.
    response = await client.post(
        upstream.rstrip('/') + '/v1/saber/responses/token-count',
        json=payload, headers=headers, timeout=60.0,
    )
    try:
        response.raise_for_status()
        adapted, metadata = apply_budget(payload, response.json())
    finally:
        await response.aclose()
    return json.dumps(adapted, ensure_ascii=False).encode('utf-8'), metadata
