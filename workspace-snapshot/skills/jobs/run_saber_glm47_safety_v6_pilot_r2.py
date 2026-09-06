"""Single-GPU diagnostic pilot. Never starts the full benchmark."""

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
SLUG = 'codex_glm47_flash_safety_v6_pilot_r2'
CONFIG = ROOT / 'jobs/saber_glm47_safety_v6_pilot_r2.json'
SUBSET = ROOT / 'jobs/saber_glm47_safety_v6_pilot_r2_subset.json'
RESULTS = SABER / 'results' / (SLUG + '_codex-native-safety-orchestrator')
MODEL = ROOT / 'models/modelscope/ZhipuAI/GLM-4.7-Flash'
VENV = ROOT / 'envs/qwen35-vllm'
LOG = ROOT / 'logs/saber-glm47-safety-v6-pilot-r2' / time.strftime('%Y%m%d-%H%M%S')
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def status(message):
    line = time.strftime('%Y-%m-%d %H:%M:%S %z') + '\t' + message
    print(line, flush=True)
    with (LOG / 'status.tsv').open('a') as handle:
        handle.write(line + '\n')


def host_path(path):
    return os.environ['HOST_USER_ROOT'].rstrip('/') + str(path)[len('/2024233123'):]


def fingerprint():
    paths = [CONFIG, SUBSET, Path(__file__),
             SABER / 'harness_adapters/codex_native_adapter.py',
             BUNDLE / 'adapters/codex/codex_hook.py']
    paths += sorted((BUNDLE / 'hooks/scripts').glob('*.py'))
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
    name = 'rick-saber-v6-r2-' + phase + '-' + LOG.name
    command = [
        'docker', 'run', '--rm', '--name', name, '--runtime', 'runc',
        '--label', 'rick-saber.pilot=' + SLUG,
        '--env', 'DOCKER_HOST=' + os.environ['DOCKER_HOST'],
        '--env', 'DOCKER_API_VERSION=1.43', '--env', 'SABER_DOCKER_RUNTIME=runc',
    ]
    for source, destination, readonly in (
        (CONFIG, '/run/secrets/saber-config.json', True),
        (SUBSET, '/run/secrets/saber-subset.json', True),
        (SABER / 'harness_adapters/codex_native_adapter.py',
         '/workspace/saber/harness_adapters/codex_native_adapter.py', True),
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
        assert meta.get('condition') == 'safety-orchestrator', (path.name, meta)
        assert meta.get('router_preloaded') is True, path.name
        assert meta.get('hooks_listed') is True, path.name
        assert meta.get('manual_hook_runs', 0) > 0, path.name
        rows.append({
            'id': result['id'], 'events': len(result.get('events') or []),
            'hook_runs': meta['manual_hook_runs'],
            'hook_blocks': meta.get('manual_hook_blocks', 0),
        })
    return rows


def main():
    assert not RESULTS.exists(), f'results already exist: {RESULTS}'
    assert len(list(MODEL.glob('model-*-of-00048.safetensors'))) == 48
    used, free, utilization = map(int, subprocess.check_output([
        'nvidia-smi', '-i', '1', '--query-gpu=memory.used,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits',
    ], text=True).strip().split(','))
    assert used < 4096 and free > 130000 and utilization < 10, (used, free, utilization)
    for port in (18002, 18003):
        with socket.socket() as sock:
            sock.bind(('0.0.0.0', port))
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
        runner('smoke', ['--skip-preflight', '--trace', 'A_fs_026'])
        smoke = RESULTS / 'A/fs_destruction/A_fs_026.json'
        status('smoke_contract=' + json.dumps(validate([smoke])))
        runner('subset', ['--skip-preflight', '--subset', '/run/secrets/saber-subset.json'])
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
