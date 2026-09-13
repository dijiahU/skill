"""Offline audit only: no trajectory commands, API, Docker, or subprocess executed.
Loads bundle pure normalization/effect functions and actual SDK executor method
with subprocess mocked to fixed harmless return values. Creates report JSON only.
"""
from __future__ import annotations
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

ROOT = Path('/srv/benchmark/skills/projects/skill-api-20260912')
BUNDLE = Path('/srv/benchmark/skills/jobs/oas-api222-20260912-r1/skills100/bundle')
OUT = Path(__file__).parent
sys.path.insert(0, str(BUNDLE / 'hooks/scripts'))
from lib_common import normalize_host_event
from write_effects import extract_write_effects

result = {'scope': 'Pinned current bundle and vendored SDK; no command execution'}
result['field_adaptation'] = []
for action in [
    {'command': 'create', 'path': '/workspace/synthetic-audit.py', 'file_text': 'value = 1\n', 'old_str': None, 'new_str': None},
    {'command': 'str_replace', 'path': '/workspace/synthetic-audit.py', 'file_text': None, 'old_str': 'value = 1', 'new_str': 'value = 2'},
]:
    raw = {'tool_name': 'file_editor', 'tool_input': action, 'cwd': '/workspace'}
    normalized = normalize_host_event(raw)
    repaired = json.loads(json.dumps(normalized))
    ti = repaired['tool_input']
    if ti.get('content') is None:
        ti.pop('content', None)
    if isinstance(ti.get('old_str'), str):
        ti['old_string'] = ti['old_str']
    result['field_adaptation'].append({
        'command': action['command'],
        'normalized_fields': {k: v for k, v in normalized['tool_input'].items() if k in ['content', 'new_string', 'old_string']},
        'effects_raw': [asdict(e) for e in extract_write_effects(raw)],
        'effects_normalized': [asdict(e) for e in extract_write_effects(normalized)],
        'effects_null_and_old_field_repaired': [asdict(e) for e in extract_write_effects(repaired)],
    })

@dataclass
class HookResult:
    success: bool = True
    blocked: bool = False
    exit_code: int = 0
    stdout: str = ''
    stderr: str = ''
    decision: str | None = None
    reason: str | None = None
    additional_context: str | None = None
    error: str | None = None
    async_started: bool = False

    @property
    def should_continue(self):
        return not self.blocked and self.decision != 'deny'

class MockTimeout(Exception):
    pass

source = ROOT / 'openagentsafety/vendor/software-agent-sdk/openhands-sdk/openhands/sdk/hooks/executor.py'
tree = ast.parse(source.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'HookExecutor')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
method.decorator_list = []
code = 'from __future__ import annotations\n' + ast.unparse(method)
mock = SimpleNamespace(TimeoutExpired=MockTimeout)
ns = {'subprocess': mock, 'json': json, 'HookResult': HookResult,
      'HookDecision': SimpleNamespace(ALLOW='allow', DENY='deny'),
      'HookType': SimpleNamespace(AGENT='agent', PROMPT='prompt'),
      'sanitized_env': lambda: {}, 'safety_orchestrator_compat_enabled': lambda: True}
exec(compile(code, str(source), 'exec'), ns)
runner = SimpleNamespace(working_dir='/workspace', async_process_manager=SimpleNamespace(cleanup_expired=lambda: None))
hook = SimpleNamespace(type='command', command='mock-only-never-executed', async_=False, timeout=60)
event = SimpleNamespace(session_id='audit', event_type='PostToolUse', tool_name='terminal', model_dump_json=lambda: '{}')
result['executor_contract'] = []
for name, rc, stdout in [
    ('exit2_block', 2, json.dumps({'verdict': 'block', 'reason': 'synthetic block'})),
    ('single_warning', 0, json.dumps({'verdict': 'warn', 'reason': 'synthetic warning'})),
    ('single_modified_output', 0, json.dumps({'modified_output': 'safe synthetic text'})),
    ('bundle_two_json_output', 0, json.dumps({'modified_output': 'safe synthetic text', 'verdicts': []}) + '\n' + json.dumps({'verdict': 'warn', 'reason': 'synthetic warning'})),
    ('timeout', None, ''),
]:
    def mock_run(*args, **kwargs):
        if rc is None:
            raise MockTimeout()
        return SimpleNamespace(returncode=rc, stdout=stdout, stderr='')
    mock.run = mock_run
    verdict = ns['execute'](runner, hook, event)
    result['executor_contract'].append({'case': name, 'result': asdict(verdict), 'should_continue': verdict.should_continue})

records = json.loads(Path('/srv/benchmark/skills/reports/oas-skills-analysis-20260913-r1/audit-records.json').read_text())
counts = {'trajectories_read': 0, 'missing_trajectories': 0, 'hook_events': 0, 'genuine_execution_errors': 0, 'modified_output_events': 0, 'modified_output_nonblock': 0, 'multi_or_truncated_json': 0, 'prepost_additional_context': 0}
for record in records:
    if record['condition'] != 'skills100':
        continue
    path = Path(record['trajectory'])
    if not path.exists():
        counts['missing_trajectories'] += 1
        continue
    counts['trajectories_read'] += 1
    for e in json.loads(path.read_text()):
        kind = e.get('hook_event_type')
        if not kind:
            continue
        counts['hook_events'] += 1
        if e.get('error') or (not e.get('success') and not e.get('blocked')):
            counts['genuine_execution_errors'] += 1
        if kind == 'PostToolUse' and '"modified_output"' in e.get('stdout', ''):
            counts['modified_output_events'] += 1
            counts['modified_output_nonblock'] += not e.get('blocked')
            try:
                json.loads(e['stdout'])
            except json.JSONDecodeError:
                counts['multi_or_truncated_json'] += 1
        if kind in ['PreToolUse', 'PostToolUse'] and e.get('additional_context'):
            counts['prepost_additional_context'] += 1
result['snapshot_audit_counts'] = counts
(OUT / 'hook-integration-reproduction.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
