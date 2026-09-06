"""Validate actual SSE text against the final response, without tool execution."""
import hashlib
import json


def stream_case(client, proxy, model_id, directory, write):
    phrase = '让我检查系统的防火墙服务状态。中文🙂'
    payload = {'model': model_id, 'input': 'Return exactly this text, without explanation: ' + phrase,
               'stream': True, 'max_output_tokens': 2048, 'store': False, 'truncation': 'disabled'}
    raw = bytearray()
    with client.stream('POST', proxy + '/responses', json=payload, timeout=240) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
    (directory / 'unicode-stream.sse').write_bytes(raw)
    text = bytes(raw).decode('utf-8', errors='strict')
    events = [json.loads(line[5:].strip()) for line in text.splitlines()
              if line.startswith('data:') and line[5:].strip() not in ('', '[DONE]')]
    errors = [event for event in events if event.get('type') in {'error', 'response.failed', 'response.incomplete'}]
    assert not errors, 'Stream contained a failed or incomplete terminal event'
    final_events = [event for event in events if event.get('type') == 'response.completed']
    assert len(final_events) == 1, 'Expected exactly one completed SSE event'
    final = final_events[0]['response']
    deltas = ''.join(event.get('delta', '') for event in events if event.get('type') == 'response.output_text.delta')
    final_text = ''.join(part.get('text', '') for item in final.get('output', [])
                         if item.get('type') == 'message' for part in item.get('content', [])
                         if part.get('type') == 'output_text')
    row = {'name': 'unicode_sse', 'event_count': len(events), 'sha256': hashlib.sha256(raw).hexdigest(),
           'byte_count': len(raw), 'delta_matches_final': deltas == final_text,
           'replacement_count': final_text.count('\ufffd'), 'expected_text_present': phrase in final_text,
           'response_status': final.get('status'), 'usage': final.get('usage')}
    write(directory / 'unicode-stream-validation.json', row)
    assert row['delta_matches_final'] and deltas, 'SSE delta text differs from final output'
    assert row['replacement_count'] == 0 and row['expected_text_present'], 'Expected multibyte text changed'
    assert row['response_status'] == 'completed'
    return {**row, 'passed': True}
