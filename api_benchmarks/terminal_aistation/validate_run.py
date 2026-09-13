"""Validate a full-treatment integration run from persisted evidence."""
import argparse
import json
from pathlib import Path


def validate(job):
    outcome = json.loads((job / 'result.json').read_text())
    stats = outcome['stats']
    issues = []
    if stats['n_errored_trials'] or stats['n_completed_trials'] != outcome['n_total_trials']:
        issues.append('incomplete_or_errored_trials')
    evidence = []
    for path in sorted(job.glob('*/agent/native-metadata.json')):
        trial = path.parent.parent
        meta = json.loads(path.read_text())
        tools = json.loads((path.parent / 'real-tool-events.json').read_text())
        checks = json.loads((trial / 'verifier/ctrf.json').read_text())['results']
        usage = meta.get('safety_usage', {})
        hooks = usage.get('hook_calls', [])
        hook_events = {item['event'] for item in hooks}
        observations = meta.get('workspace_observations', [])
        failed = [item['name'] for item in checks['tests'] if item['status'] != 'passed']
        local = []
        if meta.get('turn_status') != 'completed' or not meta.get('model_final_present'):
            local.append('model_did_not_finish_normally')
        if not tools or len(tools) != meta.get('tool_calls'):
            local.append('missing_or_mismatched_real_tool_calls')
        if not {'UserPromptSubmit','PreToolUse','PostToolUse','Stop'}.issubset(hook_events):
            local.append('missing_hook_events')
        if not meta.get('router_preloaded') or 'safety-router-skill' not in meta.get('skills', []):
            local.append('missing_router_load_evidence')
        if not usage.get('skill_reads'):
            local.append('no_observed_archetype_read')
        if not observations or any(item.get('status') != 'ready' for item in observations):
            local.append('workspace_snapshot_failure')
        if meta.get('host_tool_items'):
            local.append('unexpected_host_tool_items')
        if failed:
            local.append('official_test_failure')
        reward = (trial/'verifier/reward.txt').read_text().strip()
        if reward not in {'1','1.0'}:
            local.append('reward_not_one')
        evidence.append({'trial':trial.name, 'tool_calls':len(tools),
            'hook_calls':len(hooks), 'hook_blocks':meta.get('manual_hook_blocks'),
            'hook_events':sorted(hook_events), 'archetypes_read':usage.get('archetypes_read', []),
            'tests_passed':sum(t['status']=='passed' for t in checks['tests']),
            'tests_total':len(checks['tests']), 'failed_tests':failed, 'issues':local})
        issues.extend(f'{trial.name}:{item}' for item in local)
    if len(evidence) != outcome['n_total_trials']:
        issues.append('missing_full_treatment_trial_evidence')
    return {'passed':not issues, 'purpose':'integration_validation_not_full_benchmark_score',
            'job':str(job.resolve()), 'issues':issues, 'trials':evidence}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=validate(args.job)
    if args.output:
        with args.output.open('x') as stream: json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
