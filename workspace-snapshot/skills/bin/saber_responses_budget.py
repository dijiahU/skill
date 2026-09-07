"""Versioned exact-render budget guard, enabled only for new SABER services."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

PROTOCOL = 'saber-responses-budget-v1'


def normalize_rejected_tool_history(payload):
    """Keep explicitly rejected calls replayable without inventing a tool effect.

    Native Codex retains malformed function arguments followed by its parse
    error. Mistral's historical tool serializer requires valid JSON, even for
    these non-executed calls. Preserve the raw bytes as a JSON string field;
    never repair them into an executable command or change the matching output.
    """
    items = payload.get('input')
    if not isinstance(items, list):
        return payload
    errors = {
        item.get('call_id'): (index, item['output'])
        for index, item in enumerate(items)
        if isinstance(item, dict) and item.get('type') == 'function_call_output'
        and isinstance(item.get('call_id'), str) and item['call_id']
        and isinstance(item.get('output'), str)
    }
    adapted = list(items)
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get('type') != 'function_call':
            continue
        call_id = item.get('call_id')
        if not isinstance(call_id, str) or not call_id:
            continue
        matching = [row for row in items if isinstance(row, dict)
                    and row.get('call_id') == call_id
                    and row.get('type') in ('function_call', 'function_call_output')]
        if len(matching) != 2:
            continue
        error = errors.get(call_id)
        raw = item.get('arguments')
        if error is None or error[0] <= index or not isinstance(raw, str):
            continue
        parse_rejected = error[1].startswith('failed to parse function arguments:')
        unavailable = (item.get('name') == 'request_user_input'
                       and error[1] == 'request_user_input is unavailable in Default mode')
        name = item.get('name')
        unsupported = (isinstance(name, str) and bool(name)
                       and error[1] == f'unsupported call: {name}')
        if not (parse_rejected or unavailable or unsupported):
            continue
        try:
            invalid = not isinstance(json.loads(raw), dict)
        except json.JSONDecodeError:
            invalid = True
        if invalid:
            adapted[index] = {**item, 'arguments': json.dumps({
                '__saber_rejected_argument_history__': {
                    'raw_arguments': raw,
                    'raw_arguments_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'parse_error': error[1],
                    'rejection_kind': ('argument_parse_error' if parse_rejected else
                                       'tool_unavailable' if unavailable else 'unsupported_tool'),
                    'executed': False,
                },
            }, ensure_ascii=False)}
    return {**payload, 'input': adapted}


class ContextBudgetError(ValueError):
    pass


class TokenCountRequestError(ContextBudgetError):
    code = 'token_count_request_rejected'

    def __init__(self, response, payload):
        self.upstream_status = response.status_code
        self.request_sha256 = hashlib.sha256(json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')
        ).encode()).hexdigest()
        self.upstream_body_sha256 = hashlib.sha256(response.content).hexdigest()
        self.evidence_path = None
        evidence_dir = os.environ.get('SABER_RESPONSES_ERROR_DIR')
        if evidence_dir:
            directory = Path(evidence_dir)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f'{self.request_sha256}-{self.upstream_body_sha256}.json'
            evidence = {
                'schema': 'saber-token-count-rejection-v1',
                'request': payload, 'request_sha256': self.request_sha256,
                'upstream_status': self.upstream_status,
                'upstream_body': response.text,
                'upstream_body_sha256': self.upstream_body_sha256,
                'generation_submitted': False,
            }
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, 'w') as output:
                    json.dump(evidence, output, ensure_ascii=False, indent=2)
            self.evidence_path = str(path)
        super().__init__(
            f'Exact token-count request rejected (HTTP {response.status_code}); '
            f'generation was not submitted. Upstream diagnostic: {response.text[:8192]}'
        )


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
    payload = normalize_rejected_tool_history(payload)
    # Same adapted body is counted and subsequently submitted. No hidden history
    # truncation, extra tool execution, or generation request is used to count.
    response = await client.post(
        upstream.rstrip('/') + '/v1/saber/responses/token-count',
        json=payload, headers=headers, timeout=60.0,
    )
    try:
        if response.status_code in (400, 422):
            raise TokenCountRequestError(response, payload)
        response.raise_for_status()
        adapted, metadata = apply_budget(payload, response.json())
    finally:
        await response.aclose()
    return json.dumps(adapted, ensure_ascii=False).encode('utf-8'), metadata
