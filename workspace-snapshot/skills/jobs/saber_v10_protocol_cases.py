"""Real-service probes; tool calls are observed, never executed."""
import json


def extended_cases(client, backend, proxy, model_id, directory, write):
    rows = []
    def counted(payload, label):
        response = client.post(backend + '/v1/saber/responses/token-count', json=payload)
        write(directory / (label + '-count.json'), {'status_code': response.status_code, 'body': response.text})
        response.raise_for_status()
        return response.json()
    def generated(payload, label, through_proxy=False):
        response = client.post((proxy if through_proxy else backend + '/v1') + '/responses', json=payload, timeout=240)
        write(directory / (label + '-response.json'), {'status_code': response.status_code, 'body': response.text})
        response.raise_for_status()
        return response.json()
    text = '中文路径/防火墙/🙂'
    user = {'role': 'user', 'content': 'Call echo_text with exactly this text: ' + text}
    payload = {'model': model_id, 'input': [user], 'stream': False,
               'instructions': 'Use echo_text for the requested text. After its result arrives, report that result without calling a tool again.',
               'tools': [{'type': 'function', 'name': 'echo_text', 'description': 'Echo text. This probe never executes a shell command.',
                          'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text'], 'additionalProperties': False}}],
               'tool_choice': 'auto', 'max_output_tokens': 2048, 'store': False, 'truncation': 'disabled'}
    first_count = counted(payload, 'tool-first')
    first = generated(payload, 'tool-first')
    assert first_count['input_tokens'] == first['usage']['input_tokens'], 'Tool schema rendering count mismatch'
    calls = [item for item in first.get('output', []) if item.get('type') == 'function_call']
    assert len(calls) == 1 and calls[0]['name'] == 'echo_text', 'Expected one echo tool call'
    arguments = json.loads(calls[0]['arguments'])
    assert arguments == {'text': text}, 'Multibyte tool arguments changed'
    payload['input'] = [user, *first['output'], {'type': 'function_call_output', 'call_id': calls[0]['call_id'], 'output': json.dumps(arguments, ensure_ascii=False)}]
    second_count = counted(payload, 'tool-second')
    second = generated(payload, 'tool-second')
    assert second_count['input_tokens'] == second['usage']['input_tokens'], 'Tool history rendering count mismatch'
    assert second.get('status') == 'completed', 'Tool follow-up did not complete'
    rows.append({'name': 'multibyte_tool_roundtrip', 'passed': True, 'first_input_tokens': first_count['input_tokens'], 'second_input_tokens': second_count['input_tokens']})

    # Binary-search a rendered input just beyond the old 4096 output boundary.
    payload = {'model': model_id, 'input': 'x', 'stream': False,
               'instructions': 'The input is filler. Reply only OK.',
               'max_output_tokens': 4096, 'store': False, 'truncation': 'disabled'}
    initial = counted(payload, 'long-initial')
    target = initial['context_limit'] - 4096 + 32
    low, high, best = 1, initial['context_limit'], None
    for index in range(16):
        amount = (low + high) // 2
        payload['input'] = ' x' * amount
        response = client.post(backend + '/v1/saber/responses/token-count', json=payload)
        if not response.is_success:
            high = amount - 1
            continue
        count = response.json()
        if count['input_tokens'] > target:
            high = amount - 1
        else:
            best = (dict(payload), count)
            low = amount + 1
        if low > high:
            break
    assert best is not None and best[1]['input_tokens'] > target - 64, 'Could not construct boundary input'
    payload, count = best
    write(directory / 'long-boundary-count.json', count)
    result = generated(payload, 'long-boundary-proxy', through_proxy=True)
    usage = result.get('usage') or {}
    allocated = result.get('max_output_tokens')
    assert usage.get('input_tokens') == count['input_tokens'], 'Proxy changed or truncated input'
    assert type(allocated) is int and allocated < 4096, 'Proxy did not reduce the overflowing output budget'
    assert count['input_tokens'] + allocated + 128 <= count['context_limit'], 'Context reserve invariant failed'
    rows.append({'name': 'long_context_budget', 'passed': True, 'input_tokens': count['input_tokens'], 'allocated_output_tokens': allocated, 'context_limit': count['context_limit'], 'response_status': result.get('status')})
    return rows
