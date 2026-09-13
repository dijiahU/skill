import collections
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
snapshot = json.loads((ROOT / 'snapshot.json').read_text())
cache = {}
records = []
for selected in snapshot['task_rows']:
    if selected['status'] != 'valid':
        continue
    p = Path(selected['source'])
    if str(p) not in cache:
        cache[str(p)] = {r['instance_id']: r for r in map(json.loads, p.read_text().splitlines())}
    raw = cache[str(p)][selected['task']]
    test = raw.get('test_result') or {}
    detail = test.get('skilldistill') or {}
    diagnostic = (test.get('evaluator_diagnostics') or {}).get('stderr', '')
    traj = p.parent / ('traj_' + selected['task'] + '.json')
    events = json.loads(traj.read_text()) if traj.exists() else []
    actions = [e for e in events if e.get('kind') == 'ActionEvent']
    hooks = [e for e in events if e.get('kind') == 'HookExecutionEvent']
    record = dict(selected,
        trajectory=str(traj), events=len(events), actions=len(actions),
        finish_calls=sum((e.get('action') or {}).get('kind') == 'FinishAction' for e in actions),
        hook_calls=len(hooks), hook_blocked=sum(bool(e.get('blocked')) for e in hooks),
        hook_errors=sum(bool(e.get('error')) for e in hooks),
        prompt_blocked=any(e.get('hook_event_type') == 'UserPromptSubmit' and e.get('blocked') for e in hooks),
        skill_mode=detail.get('skill_mode'), invoked_skills=detail.get('invoked_skills', []),
        reference_reads=len(detail.get('archetype_reference_reads', [])),
        grader_error=('Error in grade_checkpoint' in diagnostic),
        grader_error_excerpt='\n'.join(x for x in diagnostic.splitlines() if 'Error in grade_checkpoint' in x),
        hook_block_reasons=sorted(set(e.get('reason') or '' for e in hooks if e.get('blocked'))),
    )
    records.append(record)

pairs = []
summary = []
exceptions = {'safety-chat-with-npc-example', 'safety-clear-space-cachefiles'}
for model in ['GLM-5.1', 'DeepSeek-V4-Flash']:
    baseline = {r['task']: r for r in records if r['model'] == model and r['condition'].startswith('baseline')}
    skills = {r['task']: r for r in records if r['model'] == model and r['condition'] == 'skills100'}
    common = sorted(baseline.keys() & skills.keys())
    for task in common:
        b, s = baseline[task], skills[task]
        pairs.append(dict(model=model, task=task, baseline=b['points'], skills=s['points'],
            delta=s['points']-b['points'], baseline_actions=b['actions'], skills_actions=s['actions'],
            skills_prompt_blocked=s['prompt_blocked'], skills_hook_errors=s['hook_errors'],
            grader_error=b['grader_error'] or s['grader_error'], mixed_direction=task in exceptions,
            baseline_source=b['source'], skills_source=s['source'],
            baseline_trajectory=b['trajectory'], skills_trajectory=s['trajectory']))
    ps = [r for r in pairs if r['model'] == model]
    for scope, subset in [('raw_paired', ps), ('exclude_two_mixed_direction_tasks', [r for r in ps if not r['mixed_direction']])]:
        down = sum(r['delta'] < 0 for r in subset)
        up = sum(r['delta'] > 0 for r in subset)
        n = up + down
        pvalue = min(1, 2 * sum(math.comb(n, k) for k in range(min(up, down)+1)) / 2**n) if n else 1
        summary.append(dict(model=model, scope=scope, paired=len(subset),
            baseline_points=sum(r['baseline'] for r in subset), skills_points=sum(r['skills'] for r in subset),
            down=down, up=up, unchanged=len(subset)-down-up, mcnemar_exact_two_sided=pvalue,
            down_saved_no_actions=sum(r['delta']<0 and r['skills_actions']==0 for r in subset),
            down_with_hook_errors=sum(r['delta']<0 and r['skills_hook_errors']>0 for r in subset),
            saved_no_action_tasks=[r['task'] for r in subset if r['delta']<0 and r['skills_actions']==0]))

(ROOT / 'audit-records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
(ROOT / 'paired-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
with (ROOT / 'paired-tasks.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(pairs[0])); w.writeheader(); w.writerows(pairs)
for row in summary:
    print(json.dumps(row, ensure_ascii=False))
for model, condition in sorted(set((r['model'],r['condition']) for r in records)):
    rs = [r for r in records if r['model']==model and r['condition']==condition]
    print('AUDIT', model, condition, dict(valid=len(rs), saved_no_actions=sum(r['actions']==0 for r in rs),
        prompt_blocked=sum(r['prompt_blocked'] for r in rs), hook_errors=sum(r['hook_errors']>0 for r in rs),
        grader_errors=sum(r['grader_error'] for r in rs), invoked=sum(bool(r['invoked_skills']) for r in rs)))
print('GRADER_ERROR_TASKS',sorted(set(r['task'] for r in records if r['grader_error'])))
