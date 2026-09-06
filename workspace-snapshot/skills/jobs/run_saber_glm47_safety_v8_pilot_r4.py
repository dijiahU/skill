"""Authorized fourth single-GPU diagnostic pilot; never runs the full benchmark."""

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
SLUG = 'codex_glm47_flash_safety_v8_pilot_r4'
CONFIG = ROOT / 'jobs/saber_glm47_safety_v8_pilot_r4.json'
SUBSET = ROOT / 'jobs/saber_glm47_safety_v8_pilot_r4_subset.json'
RESULTS = SABER / 'results' / (SLUG + '_codex-native-safety-orchestrator')
MODEL = ROOT / 'models/modelscope/ZhipuAI/GLM-4.7-Flash'
VENV = ROOT / 'envs/qwen35-vllm'
LOG = ROOT / 'logs/saber-glm47-safety-v8-pilot-r4' / time.strftime('%Y%m%d-%H%M%S')
RUNNERS = {phase: 'rick-saber-v8-r4-' + phase + '-20260905'
           for phase in ('preflight', 'smoke', 'subset')}
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
EXPECTED = {
    BUNDLE / 'hooks/scripts/matcher_stop.py': '4e1a8b1198a36194c12885792e3039242f748d082378b8123ee3b9e1e1afb2b1',
    BUNDLE / 'hooks/scripts/output_proposals.py': 'c7eb7e7ed1194ed90a144b87a1a2dfbaef4255531f20445b35d84e16408508c7',
    BUNDLE / 'hooks/scripts/matcher_bash.py': 'c4c7e2ebf854b1d08e5b8e77ae3f4b3c17c85d7e9e495f9d31709cf885e55769',
    SABER / 'harness_adapters/codex_native_adapter.py': '22bfe4f4c8d42542ab7484ecd54188c4d47a51cfa9caa1138bbb4d052a8a22fe',
}


def status(message):
    line = time.strftime('%Y-%m-%d %H:%M:%S %z') + '\t' + message
    print(line, flush=True)
    with (LOG / 'status.tsv').open('a') as handle:
        handle.write(line + '\n')


def host_path(path):
    path = Path(path)
    relative = path.relative_to(os.environ['POD_USER_ROOT'])
    return str(Path(os.environ['HOST_USER_ROOT']) / relative)


def fingerprint():
    paths = [CONFIG, SUBSET, Path(__file__),
             SABER / 'harness_adapters/codex_native_adapter.py', SABER / 'sandbox_shell.py',
             BUNDLE / 'adapters/codex/codex_hook.py']
    paths += sorted((BUNDLE / 'hooks/scripts').glob('*.py'))
    paths += sorted((BUNDLE / 'helpers').rglob('*.py'))
    paths += sorted((BUNDLE / 'skills/safety-router-skill').rglob('*.md'))
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


def validate(paths):
    rows = []
    for path in paths:
        result = json.loads(path.read_text())
        meta = result.get('harness_meta') or {}
        assert not result.get('error'), (path.name, result.get('error'))
        assert meta.get('condition') == 'safety-orchestrator', path.name
        assert meta.get('router_preloaded') is True, path.name
        assert meta.get('hooks_listed') is True, path.name
        assert meta.get('manual_hook_runs', 0) > 0, path.name
        assert meta.get('safety_workspace_snapshot_mode') == 'live-before-pretool', path.name
        assert meta.get('stop_workspace_snapshot') is True, path.name
        assert meta.get('stop_workspace_guard_blocks', 0) == 0, path.name
        observations = meta.get('workspace_observations') or []
        assert observations and all(row.get('status') == 'ready' for row in observations), (path.name, observations)
        rows.append({
            'id': result['id'], 'events': len(result.get('events') or []),
            'hook_runs': meta['manual_hook_runs'],
            'hook_blocks': meta.get('manual_hook_blocks', 0),
            'workspace_observations': len(observations),
            'stop_workspace_snapshot': meta['stop_workspace_snapshot'],
        })
    return rows


def main():
    assert not RESULTS.exists(), f'results already exist: {RESULTS}'
    assert len(json.loads(SUBSET.read_text())['tasks']) == 12
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
    subprocess.run(['docker', 'image', 'inspect', 'saber-codex-runner:0.149.1',
                    'osbench-sandbox:latest'], stdout=subprocess.DEVNULL, check=True)
    LOG.mkdir(parents=True, exist_ok=False)
    before = fingerprint()
    (LOG / 'code-fingerprint-before.json').write_text(json.dumps(before, indent=2))
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
        status(f'vllm_start gpu=1 pid={server.pid} log={LOG}')
        await_ready(server, 'http://127.0.0.1:18002/health', 900)
        with (LOG / 'proxy.log').open('x') as output:
            proxy = subprocess.Popen([
                str(VENV / 'bin/python'), str(ROOT / 'bin/vllm_responses_compat_proxy_glm47.py'),
                '--host', '0.0.0.0', '--port', '18003',
                '--upstream', 'http://127.0.0.1:18002',
            ], stdout=output, stderr=subprocess.STDOUT)
        services.append(proxy)
        await_ready(proxy, 'http://127.0.0.1:18003/v1/models', 60)
        (LOG / 'service-pids.json').write_text(json.dumps([p.pid for p in services]))
        status('services_ready')
        runner('preflight', ['--preflight-only', 'A_fs_026'])
        assert before == fingerprint(), 'code changed before smoke'
        runner('smoke', ['--skip-preflight', '--trace', 'A_fs_026'])
        smoke = RESULTS / 'A/fs_destruction/A_fs_026.json'
        status('smoke_contract=' + json.dumps(validate([smoke])))
        assert before == fingerprint(), 'code changed before subset'
        runner('subset', ['--skip-preflight', '--trace', '--subset', '/run/secrets/saber-subset.json'])
        paths = sorted(RESULTS.rglob('*.json'))
        assert len(paths) == 12, len(paths)
        rows = validate(paths)
        (LOG / 'harness-validation.json').write_text(json.dumps(rows, indent=2))
        after = fingerprint()
        (LOG / 'code-fingerprint-after.json').write_text(json.dumps(after, indent=2))
        assert before == after, 'code changed during pilot'
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
        status('pilot_exit')


if __name__ == '__main__':
    main()
