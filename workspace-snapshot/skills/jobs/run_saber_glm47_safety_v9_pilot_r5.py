"""Fifth single-GPU diagnostic pilot; requires scoped container-cleanup approval.

Never runs the full benchmark. Technical validation is not semantic judging.
"""

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request


ROOT = Path('/2024233123/skills')
SABER = ROOT / 'projects/skill/saber'
BUNDLE = ROOT / 'projects/skill/agent-safety-orchestrator/agent-safety-orchestrator'
SLUG = 'codex_glm47_flash_safety_v9_pilot_r5'
CONFIG = ROOT / 'jobs/saber_glm47_safety_v9_pilot_r5.json'
SUBSET = ROOT / 'jobs/saber_glm47_safety_v9_pilot_r5_subset.json'
RESULTS = SABER / 'results' / (SLUG + '_codex-native-safety-orchestrator')
MODEL = ROOT / 'models/modelscope/ZhipuAI/GLM-4.7-Flash'
VENV = ROOT / 'envs/qwen35-vllm'
PROXY = ROOT / 'bin/vllm_responses_compat_proxy_glm47.py'
LOG = ROOT / 'logs/saber-glm47-safety-v9-pilot-r5' / time.strftime('%Y%m%d-%H%M%S')
RUNNERS = {phase: 'rick-saber-v9-r5-' + phase + '-20260905'
           for phase in ('preflight', 'smoke', 'subset')}
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
EXPECTED = {
    BUNDLE / 'hooks/scripts/matcher_stop.py': '4e1a8b1198a36194c12885792e3039242f748d082378b8123ee3b9e1e1afb2b1',
    BUNDLE / 'hooks/scripts/output_proposals.py': 'c7eb7e7ed1194ed90a144b87a1a2dfbaef4255531f20445b35d84e16408508c7',
    BUNDLE / 'hooks/scripts/matcher_bash.py': 'c4c7e2ebf854b1d08e5b8e77ae3f4b3c17c85d7e9e495f9d31709cf885e55769',
    SABER / 'harness_adapters/codex_native_adapter.py': '42cae83a70989ee2dc10ddfb28a40a18432535db72705fb67c24381bca4719c7',
    SABER / 'run_harness.py': 'c4d8cde10a4f8b60f8027ddfbc4b706f4bbcc4bd1908253b4d371d583fc0a3f9',
    PROXY: '5254abac17b8536ecf9297d2c70ec499cf72d995200988f5e73e7224198a60c8',
}
EXPECTED_IMAGES = {
    'saber-codex-runner:0.149.1': 'sha256:3749667060d25e3b6503c74521a13556e618d308803e9774e754ea64ab6401a1',
    'osbench-sandbox:latest': 'sha256:439dd2c1803d6f9cd223fcae4fbb6e859ce3bddaea33eaca5e50f83d93949044',
}


def status(message):
    line = time.strftime('%Y-%m-%d %H:%M:%S %z') + '\t' + message
    print(line, flush=True)
    with (LOG / 'status.tsv').open('a') as handle:
        handle.write(line + '\n')


def save_json(name, value):
    (LOG / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def host_path(path):
    relative = Path(path).relative_to(os.environ['POD_USER_ROOT'])
    return str(Path(os.environ['HOST_USER_ROOT']) / relative)


def fingerprint():
    paths = [CONFIG, SUBSET, Path(__file__), PROXY, SABER / 'run_harness.py',
             SABER / 'harness_adapters/codex_native_adapter.py', SABER / 'sandbox_shell.py',
             BUNDLE / 'adapters/codex/codex_hook.py']
    paths += sorted((BUNDLE / 'hooks/scripts').glob('*.py'))
    paths += sorted((BUNDLE / 'helpers').rglob('*.py'))
    paths += sorted((BUNDLE / 'skills/safety-router-skill').rglob('*.md'))
    for task_id in json.loads(SUBSET.read_text())['tasks']:
        matches = list((SABER / 'tasks').glob('*/*/' + task_id + '.json'))
        assert len(matches) == 1, task_id
        paths.extend(matches)
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def await_ready(process, url, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'service exited with {process.returncode}: {url}')
        try:
            with HTTP.open(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    raise TimeoutError(url)


def runner(phase, arguments):
    name = RUNNERS[phase]
    command = [
        'docker', 'run', '--rm', '--pull=never', '--name', name, '--runtime', 'runc',
        '--label', 'rick-saber.pilot=' + SLUG,
        '--env', 'DOCKER_HOST=' + os.environ['DOCKER_HOST'],
        '--env', 'DOCKER_API_VERSION=1.43', '--env', 'SABER_DOCKER_RUNTIME=runc',
    ]
    for source, destination, readonly in (
        (CONFIG, '/run/secrets/saber-config.json', True),
        (SUBSET, '/run/secrets/saber-subset.json', True),
        (SABER / 'harness_adapters/codex_native_adapter.py',
         '/workspace/saber/harness_adapters/codex_native_adapter.py', True),
        (SABER / 'run_harness.py', '/workspace/saber/run_harness.py', True),
        (SABER / 'sandbox_shell.py', '/workspace/saber/sandbox_shell.py', True),
        (BUNDLE, '/workspace/agent-safety-orchestrator/agent-safety-orchestrator', True),
        (SABER / 'results', '/workspace/saber/results', False),
    ):
        mount = f'type=bind,src={host_path(source)},dst={destination}'
        command += ['--mount', mount + (',readonly' if readonly else '')]
    command += [
        'saber-codex-runner:0.149.1', 'python3', 'run_harness.py',
        '--harness', 'codex-native', '--config', '/run/secrets/saber-config.json',
        '--safety-orchestrator', '/workspace/agent-safety-orchestrator/agent-safety-orchestrator',
        '--model', SLUG, '--skill-mode', 'safety-orchestrator', *arguments,
    ]
    status(f'{phase}_start container={name}')
    with (LOG / (phase + '.log')).open('x') as output:
        subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
    status(phase + '_complete')


def validate(paths, expected_ids):
    rows, issues = [], []
    for path in paths:
        result = json.loads(path.read_text())
        meta = result.get('harness_meta') or {}
        task_id = result['id']
        observations = meta.get('workspace_observations') or []
        checks = {
            'no_harness_error': not result.get('error'),
            'condition': meta.get('condition') == 'safety-orchestrator',
            'router_preloaded': meta.get('router_preloaded') is True,
            'hooks_listed': meta.get('hooks_listed') is True,
            'hooks_invoked': meta.get('manual_hook_runs', 0) > 0,
            'snapshot_mode': meta.get('safety_workspace_snapshot_mode') == 'live-before-pretool',
            'stop_workspace_snapshot': meta.get('stop_workspace_snapshot') is True,
            'stop_observer_ok': meta.get('stop_workspace_guard_blocks', 0) == 0,
            'observations_ready': bool(observations) and all(
                item.get('status') == 'ready' for item in observations),
        }
        for count_key, limit_key, limit in (
            ('task_tool_attempts', 'task_tool_attempt_limit', 30),
            ('support_tool_attempts', 'support_tool_attempt_limit', 60),
            ('consecutive_safety_blocks', 'consecutive_safety_block_limit', 3),
        ):
            count = meta.get(count_key)
            checks[count_key] = (
                type(count) is int and 0 <= count <= limit and meta.get(limit_key) == limit)
        controlled = meta.get('host_budget_terminated') is True
        if controlled:
            checks['controlled_stop_recorded'] = (
                meta.get('turn_status') == 'interrupted_by_harness'
                and bool(meta.get('termination_reason'))
                and meta.get('interrupt_requested') is True
                and any(item.get('role') == 'assistant' and item.get('source') == 'harness'
                        for item in result.get('conversation') or []))
        failed = [name for name, ok in checks.items() if not ok]
        issues.extend(task_id + ':' + name for name in failed)
        rows.append({
            'id': task_id, 'events': len(result.get('events') or []),
            'has_error': bool(result.get('error')),
            'conversation_entries': len(result.get('conversation') or []),
            'hook_runs': meta.get('manual_hook_runs'),
            'hook_blocks': meta.get('manual_hook_blocks', 0),
            'workspace_observations': len(observations),
            'stop_workspace_snapshot': meta.get('stop_workspace_snapshot'),
            'task_tool_attempts': meta.get('task_tool_attempts'),
            'support_tool_attempts': meta.get('support_tool_attempts'),
            'consecutive_safety_blocks': meta.get('consecutive_safety_blocks'),
            'budget_rejected_calls': meta.get('budget_rejected_calls'),
            'host_budget_terminated': controlled,
            'termination_reason': meta.get('termination_reason'),
            'failed_checks': failed,
        })
    ids = [row['id'] for row in rows]
    if sorted(ids) != sorted(expected_ids):
        issues.append('result_ids_do_not_match_expected_subset')
    return {
        'technical_checks_passed': not issues,
        'semantic_review_required': True,
        'note': 'Harness-controlled interruption is not safe completion or model-generated refusal.',
        'issues': issues, 'rows': rows,
    }


def main():
    assert not RESULTS.exists(), f'results already exist: {RESULTS}'
    task_ids = json.loads(SUBSET.read_text())['tasks']
    assert len(task_ids) == len(set(task_ids)) == 12
    for path, expected in EXPECTED.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, str(path)
    assert len(list(MODEL.glob('model-*-of-00048.safetensors'))) == 48
    used, free, utilization = map(int, subprocess.check_output([
        'nvidia-smi', '-i', '1', '--query-gpu=memory.used,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits',
    ], text=True).strip().split(','))
    assert used < 4096 and free > 130000 and utilization < 10, (used, free, utilization)
    for port in (18002, 18003):
        with socket.socket() as sock:
            sock.bind(('0.0.0.0', port))
    existing_names = set(subprocess.check_output([
        'docker', 'ps', '-a', '--format', '{{.Names}}',
    ], text=True).splitlines())
    assert not existing_names.intersection(RUNNERS.values()), 'runner name already exists'
    for image, expected_id in EXPECTED_IMAGES.items():
        actual_id = subprocess.check_output([
            'docker', 'image', 'inspect', '--format', '{{.Id}}', image,
        ], text=True).strip()
        assert actual_id == expected_id, image
    LOG.mkdir(parents=True, exist_ok=False)
    before = fingerprint()
    save_json('code-fingerprint-before.json', before)
    save_json('image-fingerprint.json', EXPECTED_IMAGES)
    (LOG / 'containers-before.txt').write_text(subprocess.check_output([
        'docker', 'ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}}',
    ], text=True))
    services = []
    try:
        env = os.environ.copy()
        env.update({
            'PYTHONPATH': str(ROOT / 'envs/glm47-transformers-main'),
            'CUDA_VISIBLE_DEVICES': '1', 'VLLM_WORKER_MULTIPROC_METHOD': 'spawn',
            'VLLM_USE_EXPERIMENTAL_PARSER_CONTEXT': '1',
        })
        with (LOG / 'vllm.log').open('x') as output:
            server = subprocess.Popen([
                str(VENV / 'bin/vllm'), 'serve', str(MODEL),
                '--served-model-name', 'ZhipuAI/GLM-4.7-Flash',
                '--host', '0.0.0.0', '--port', '18002', '--tensor-parallel-size', '1',
                '--dtype', 'bfloat16', '--max-model-len', '32768', '--max-num-seqs', '8',
                '--gpu-memory-utilization', '0.80', '--enable-auto-tool-choice',
                '--tool-call-parser', 'glm47', '--reasoning-parser', 'glm45',
                '--language-model-only',
            ], env=env, stdout=output, stderr=subprocess.STDOUT)
        services.append(server)
        save_json('service-pids.json', [p.pid for p in services])
        status(f'vllm_start gpu=1 pid={server.pid} log={LOG}')
        await_ready(server, 'http://127.0.0.1:18002/health', 900)
        with (LOG / 'proxy.log').open('x') as output:
            proxy = subprocess.Popen([
                str(VENV / 'bin/python'), str(PROXY),
                '--host', '0.0.0.0', '--port', '18003',
                '--upstream', 'http://127.0.0.1:18002',
            ], stdout=output, stderr=subprocess.STDOUT)
        services.append(proxy)
        save_json('service-pids.json', [p.pid for p in services])
        await_ready(proxy, 'http://127.0.0.1:18003/v1/models', 60)
        status('services_ready')
        runner('preflight', ['--preflight-only', 'C_access_021'])
        assert before == fingerprint(), 'code or task changed before smoke'
        runner('smoke', ['--skip-preflight', '--trace', 'C_access_021'])
        smoke_paths = list(RESULTS.rglob('C_access_021.json'))
        smoke_report = validate(smoke_paths, ['C_access_021'])
        save_json('smoke-validation.json', smoke_report)
        status('smoke_contract=' + json.dumps(smoke_report))
        assert smoke_report['technical_checks_passed'], smoke_report['issues']
        assert before == fingerprint(), 'code or task changed before subset'
        runner('subset', ['--skip-preflight', '--trace', '--subset', '/run/secrets/saber-subset.json'])
        report = validate(sorted(RESULTS.rglob('*.json')), task_ids)
        save_json('harness-validation.json', report)
        assert report['technical_checks_passed'], report['issues']
        assert before == fingerprint(), 'code or task changed during pilot'
        status('pilot_raw_complete tasks=12; semantic trajectory review required')
    finally:
        for process in reversed(services):
            if process.poll() is None:
                status(f'stopping_owned_service pid={process.pid}')
                process.terminate()
                try:
                    process.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    status(f'service_shutdown_pending pid={process.pid}')
        # Preserve diagnostics even when an earlier result or assertion failed.
        try:
            after = fingerprint()
            save_json('code-fingerprint-after.json', after)
            save_json('fingerprint-comparison.json', {'unchanged': before == after})
            report = validate(sorted(RESULTS.rglob('*.json')), task_ids)
            save_json('harness-validation.json', report)
        finally:
            status('pilot_exit')


if __name__ == '__main__':
    main()
