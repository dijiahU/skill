import collections
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
PREV = ROOT.parent / 'oas-skills-analysis-20260913-r1'
records = json.loads((PREV / 'audit-records.json').read_text())
output = []
for rec in records:
    if rec['condition'] != 'skills100':
        continue
    events = json.loads(Path(rec['trajectory']).read_text()) if Path(rec['trajectory']).exists() else []
    actions = [e for e in events if e.get('kind') == 'ActionEvent']
    hooks = [e for e in events if e.get('kind') == 'HookExecutionEvent']
    pre = [e for e in hooks if e.get('hook_event_type') == 'PreToolUse']
    by_action = collections.defaultdict(list)
    for h in pre:
        by_action[h.get('action_id')].append(h)
    specialized_missing = collections.Counter()
    action_tools = collections.Counter()
    scripts = collections.Counter(Path(h.get('hook_command','').split('/')[-1]).name for h in pre)
    covered = 0
    for action in actions:
        action_tools[action.get('tool_name')] += 1
        hs = by_action[action.get('id')]
        covered += bool(hs)
        name = action.get('tool_name')
        expected = 'matcher_bash.py' if name == 'terminal' else 'matcher_write_edit.py' if name == 'file_editor' else None
        if expected and not any(expected in h.get('hook_command','') for h in hs):
            specialized_missing[name] += 1
    output.append(dict(model=rec['model'], task=rec['task'], raw_score=rec['points'],
        stage=rec['stage'], trajectory=rec['trajectory'], loaded_mode=rec['skill_mode'],
        invoked=bool(rec['invoked_skills']), reference_reads=rec['reference_reads'],
        saved_actions=len(actions), saved_finish=rec['finish_calls'], saved_pre_hooks=len(pre),
        actions_with_pre=covered, missing_specialized=dict(specialized_missing),
        tools=dict(action_tools), pre_scripts=dict(scripts),
        blocked=sum(bool(h.get('blocked')) for h in hooks),
        pre_blocked=sum(bool(h.get('blocked')) for h in pre),
        failed_hooks=sum(h.get('success') is False for h in hooks),
        hook_explicit_errors=sum(bool(h.get('error')) for h in hooks),
        warn_hooks=sum('"verdict": "warn"' in (h.get('stdout') or '') for h in hooks),
        grader_error=rec['grader_error']))
(ROOT / 'coverage-records.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
summary=[]
for model in sorted(set(r['model'] for r in output)):
    for scope in ['all','raw_score_1']:
        rows=[r for r in output if r['model']==model and (scope=='all' or r['raw_score']==1)]
        total=sum(r['saved_actions'] for r in rows)
        entry=dict(model=model,scope=scope,tasks=len(rows),router_invoked=sum(r['invoked'] for r in rows),
            reference_read_tasks=sum(r['reference_reads']>0 for r in rows),saved_finish_tasks=sum(r['saved_finish']>0 for r in rows),
            saved_actions=total,actions_with_pre=sum(r['actions_with_pre'] for r in rows),
            pre_blocks=sum(r['pre_blocked'] for r in rows),block_tasks=sum(r['blocked']>0 for r in rows),
            failed_hook_tasks=sum(r['failed_hooks']>0 for r in rows),warn_tasks=sum(r['warn_hooks']>0 for r in rows))
        summary.append(entry)
        print(json.dumps(entry,ensure_ascii=False))
(ROOT / 'coverage-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
