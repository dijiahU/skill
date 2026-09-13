"""Exercise the actual adapter and all four hooks, with no model calls."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

JOB = Path(__file__).resolve().parent
os.environ['TERMINAL_BENCH_SABER_ROOT'] = str(JOB / 'frozen/saber')
sys.path.insert(0, str(JOB / 'frozen/adapter'))
from full_agent import HarborRuntime, RetainedAdapter


class RetainedEnvironment:
    def __init__(self, container):
        self.container = container

    async def _run_docker_compose_command(self, command, **kwargs):
        assert command[:5] == ['exec', '-T', '-w', '/app', 'main']
        return await self._run(['docker', 'exec', '-i', '-w', '/app', self.container, *command[5:]],
                               kwargs['stdin_data'], kwargs['timeout_sec'])

    async def exec(self, command, cwd, timeout_sec):
        return await self._run(['docker', 'exec', '-w', cwd, self.container, 'bash', '-c', command], None, timeout_sec)

    async def _run(self, argv, data, timeout):
        proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(data), timeout)
        return SimpleNamespace(stdout=out.decode(), stderr=err.decode(), return_code=proc.returncode)


def validate(task, container, loop):
    directory = JOB / 'preflight' / (task + '-hooks')
    directory.mkdir()
    adapter = RetainedAdapter(artifact_dir=directory, safety_bundle=JOB / 'frozen/safety-bundle',
                              skill_mode='safety-orchestrator', max_steps=1000)
    env, _, skill, _ = adapter._prepare_environment(directory / 'session',
                                                   {'base_url': 'http://127.0.0.1:1/v1', 'copy_codex_auth': False})
    env['SAFETY_ORCH_STRICT_SCOPE_GUARD'] = '1'
    env['SAFETY_ORCH_FAIL_CLOSED'] = '1'
    env['SAFETY_ORCH_WORKSPACE_SNAPSHOT'] = str(directory / 'workspace.json')
    adapter._write_workspace_snapshot(Path(env['SAFETY_ORCH_WORKSPACE_SNAPSHOT']), {
        'schema_version': 2, 'authoritative': True, 'snapshot_status': 'unavailable',
        'cwd': '/app', 'file_contents': {}, 'policy_file_contents': {}, 'policy_initialized': False,
        'observed_paths': [], 'observation_index': 0})
    runtime = HarborRuntime(RetainedEnvironment(container), loop, '/app', directory)
    command = "stat -c '%n %s' /app"
    common = {'cwd': '/app', 'turn_id': task, 'session_id': task,
              'tool_name': 'saber_bash', 'tool_input': {'command': command}, 'tool_call_id': 'read-only-probe'}
    timings = {}
    for event in ['UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop']:
        start = time.monotonic()
        if event in ['PreToolUse', 'Stop']:
            adapter._refresh_workspace_snapshot(runtime, '/app', env)
        timings[event + '_snapshot'] = time.monotonic() - start
        payload = dict(common, hook_event_name=event, prompt='Read-only inspection of /app directory metadata.',
                       last_assistant_message='Inspected the directory metadata with stat.')
        if event == 'PostToolUse':
            payload['tool_response'] = runtime.execute_tool('bash', {'command': command})
        start = time.monotonic()
        result = adapter._invoke_safety_hook(task, payload, env)
        timings[event + '_hook'] = time.monotonic() - start
        (directory / 'progress.json').write_text(json.dumps({'event': event, 'timings': timings,
                                                            'blocked': result.blocked, 'reason': result.reason}, indent=2))
        assert not result.blocked, (event, result.reason)
    evidence = {'task': task, 'model_api_calls': 0, 'timings': timings,
                'hooks': adapter.safety_hook_calls, 'observations': adapter.last_run_meta['workspace_observations'],
                'real_tool_events': runtime.events}
    (directory / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({'task': task, 'timings': timings, 'hooks_passed': len(adapter.safety_hook_calls)}), flush=True)


async def main():
    for task, container in [('csv', '69743bef8427'), ('ppm', '01ec73737cf0'), ('c4', 'cbfd1f467246')]:
        await asyncio.to_thread(validate, task, container, asyncio.get_running_loop())


if __name__ == '__main__':
    asyncio.run(main())
