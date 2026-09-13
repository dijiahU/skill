"""CPU-only full installation and real bridge denial check; never runs the denied command."""
import json
import os
from pathlib import Path
import tempfile
from full_agent import RetainedAdapter, BUNDLE

root = Path('/srv/benchmark/skills/reports/terminal-bench')
root.mkdir(parents=True, exist_ok=True)
report_dir = Path(tempfile.mkdtemp(prefix='full-deployment-', dir=root))
adapter = RetainedAdapter(artifact_dir=report_dir, skill_mode='safety-orchestrator', safety_bundle=BUNDLE)
session = report_dir / 'isolated'
env, workspace, skill_root, copied = adapter._prepare_environment(session, {
    'id': 'OpenAI-Mirror/gpt-oss-120b', 'base_url': 'http://127.0.0.1:18105/v1', 'copy_codex_auth': False})
health = adapter._run_skill_health(skill_root, env)
result = adapter._invoke_safety_hook('installation-canary', {
    'hook_event_name': 'PreToolUse', 'tool_name': 'saber_bash',
    'tool_input': {'command': 'rm -rf /'}, 'cwd': '/app',
    'session_id': 'installation-canary', 'turn_id': 'installation-canary'}, env)
report = {'router_installed': (skill_root/'SKILL.md').is_file(),
    'archetype_count': len(list((skill_root/'references/archetypes').glob('*.md'))),
    'hooks_installed': (session/'codex-home/hooks.json').is_file(),
    'personal_auth_copied': copied, 'health': health,
    'denial_check': {'blocked': result.blocked, 'reason': result.reason,
                     'command_executed': False, 'hook_calls': adapter.safety_hook_calls}}
(report_dir/'report.json').write_text(json.dumps(report,indent=2))
assert report['router_installed'] and report['archetype_count']==14 and report['hooks_installed']
assert not copied and result.blocked
print(report_dir/'report.json')
print('Full installation and actual PreToolUse denial passed; no denied command was executed.')
