"""Provider health checks and result selection for a resumable OAS run."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

JOB = Path(__file__).resolve().parent
RESULTS = Path('/srv/benchmark/skills/results/oas-api222-20260912-r1/baseline100')


def valid(row):
    test = row.get('test_result') or {}
    score = test.get('final_score') or {}
    return (not row.get('error')
            and not (test.get('skilldistill') or {}).get('graded_from_partial_trajectory')
            and isinstance(score.get('result'), (int, float))
            and isinstance(score.get('total'), (int, float)) and score['total'] > 0)


def read_stage(model, stage):
    root = RESULTS / model / stage
    paths = list(root.rglob('output.critic_attempt_1.jsonl')) or list(root.rglob('output.jsonl'))
    rows = {}
    for path in paths:
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # An append may still be in flight.
            rows[row['instance_id']] = row
    return rows


def balance_error(row):
    test = row.get('test_result') or {}
    # Use structured transport errors, never arbitrary benchmark prompt text.
    error = ' '.join(str(x or '') for x in [row.get('error'), (test.get('skilldistill') or {}).get('conversation_error')]).lower()
    return 'account balance is insufficient' in error


def probe(model):
    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': 'OK'}],
                       'max_tokens': 1, 'stream': False, 'enable_thinking': False}).encode()
    request = urllib.request.Request('https://api.siliconflow.cn/v1/chat/completions', data=body,
        headers={'Authorization': 'Bearer ' + os.environ['SILICONFLOW_API_KEY'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            outcome = {'http_status': response.status, 'ok': response.status == 200, 'balance_exhausted': False}
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read())
        except (ValueError, UnicodeError):
            detail = {}
        exhausted = exc.code == 402 and (detail.get('code') == 30001 or 'balance is insufficient' in str(detail.get('message', '')).lower())
        outcome = {'http_status': exc.code, 'provider_code': detail.get('code'), 'ok': False, 'balance_exhausted': exhausted}
    except Exception as exc:
        outcome = {'ok': False, 'balance_exhausted': False, 'error_type': type(exc).__name__}
    outcome.update(model=model, checked_at=time.time())
    return outcome
