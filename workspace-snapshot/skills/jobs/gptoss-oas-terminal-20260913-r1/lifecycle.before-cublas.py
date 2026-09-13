"""Own one GPU service and its complete benchmark consumer lifecycle."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request

JOB = Path(__file__).resolve().parent
BASE = Path('/srv/benchmark/skills')


def save(path, data):
    temp = path.with_suffix('.writing')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm', choices=['oas', 'terminal'], required=True)
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    arm, attempt = args.arm, args.attempt
    gpu, port = (0, 18404) if arm == 'oas' else (1, 18414)
    if os.environ.get('CUDA_VISIBLE_DEVICES') != str(gpu):
        raise RuntimeError('Requires the matching gpu-idle reservation')
    lock = (JOB / f'lifecycle-{arm}.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = JOB / f'lifecycle-{arm}.json'
    if path.exists():
        prior = json.loads(path.read_text())
        if attempt <= prior.get('attempt', 1) or not prior.get('services_released_at'):
            raise RuntimeError('Existing lifecycle is not safely retryable')
        if (JOB / f'state-{arm}.json').exists():
            raise RuntimeError('Consumer already started; requires explicit resume review')
        save(JOB / f'lifecycle-{arm}-attempt{prior.get("attempt", 1)}.json', prior)
    state = {'arm': arm, 'gpu': gpu, 'status': 'starting service', 'processes': [], 'attempt': attempt, 'enforce_eager': True}
    procs = []
    def persist():
        state['updated_at'] = time.time()
        state['processes'] = [{'name': n, 'pid': p.pid, 'returncode': p.poll()} for n, p in procs]
        save(path, state)
    def launch(name, argv, env):
        with (JOB / 'logs' / f'{arm}-{name}-attempt{attempt}.log').open('x') as log:
            p = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        procs.append((name, p))
        persist()
        return p
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    env = dict(os.environ)
    for k in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
        env.pop(k, None)
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', VLLM_NO_USAGE_STATS='1',
               VLLM_WORKER_MULTIPROC_METHOD='spawn', OMP_NUM_THREADS='8', PYTHONFAULTHANDLER='1',
               VLLM_CACHE_ROOT=str(JOB / 'cache' / arm / 'vllm'),
               TORCHINDUCTOR_CACHE_DIR=str(JOB / 'cache' / arm / 'torchinductor'),
               PYTHONPATH=str(JOB / 'frozen/service-code') + ':' + str(BASE / 'envs/gptoss-oss-harmony-overlay'),
               GPTOSS_DEBUG_REQUEST=str(JOB / 'logs' / f'{arm}-last-filtered-request.json'),
               SABER_RESPONSES_ERROR_DIR=str(JOB / 'logs' / f'{arm}-count-rejections'))
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    persist()
    try:
        for value in [port, port + 1]:
            with socket.socket() as s:
                s.bind(('0.0.0.0', value))
        services = [
            ('vllm', [str(BASE / 'envs/qwen35-vllm/bin/vllm'), 'serve',
                       str(BASE / 'models/modelscope/OpenAI-Mirror/gpt-oss-120b'),
                       '--served-model-name', 'OpenAI-Mirror/gpt-oss-120b', '--host', '127.0.0.1',
                       '--port', str(port), '--tensor-parallel-size', '1', '--max-model-len', '32768',
                       '--max-num-seqs', '8', '--gpu-memory-utilization', '0.85',
                       '--enforce-eager', '--max-num-batched-tokens', '2048',
                       '--enable-auto-tool-choice', '--tool-call-parser', 'openai', '--language-model-only',
                       '--middleware', 'saber_vllm_token_count.TokenCountMiddleware'],
             f'http://127.0.0.1:{port}/health', 1200),
            ('proxy', [str(BASE / 'envs/qwen35-vllm/bin/python'),
                       str(JOB / 'frozen/service-code/vllm_responses_compat_proxy_gptoss.py'),
                       '--host', '0.0.0.0' if arm == 'oas' else '127.0.0.1', '--port', str(port + 1),
                       '--upstream', f'http://127.0.0.1:{port}'],
             f'http://127.0.0.1:{port + 1}/v1/models', 60),
        ]
        for name, argv, url, timeout in services:
            state['status'] = 'loading ' + name
            se = dict(env, SABER_RESPONSES_CONTEXT_GUARD='1')
            proc = launch(name, argv, se)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(name + ' exited during startup')
                try:
                    with http.open(url, timeout=3) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                persist()
                time.sleep(3)
            else:
                raise TimeoutError(name + ' did not become healthy')
        pod_ip = socket.gethostbyname(socket.gethostname())
        if arm == 'oas' and pod_ip.startswith('127.'):
            raise RuntimeError('OAS task containers require a routable Pod address')
        consumer_env = dict(os.environ, GPTOSS_BASE_URL=f'http://{pod_ip if arm == "oas" else "127.0.0.1"}:{port + 1}/v1',
                            RESPONSES_API_KEY='EMPTY', OPENHANDS_SUPPRESS_BANNER='1', LITELLM_LOCAL_MODEL_COST_MAP='True')
        state.update(status='running benchmark controller', base_url=consumer_env['GPTOSS_BASE_URL'])
        consumer = launch('consumer', [str(BASE / 'envs/api-saber-20260912/bin/python'), '-u',
                                       str(JOB / 'arm_runner.py'), '--arm', arm], consumer_env)
        while consumer.poll() is None:
            if any(p.poll() is not None for n, p in procs if n != 'consumer'):
                raise RuntimeError('Model service exited during evaluation')
            persist()
            time.sleep(10)
        state.update(status='consumer ended; inspect benchmark state', consumer_returncode=consumer.returncode)
        persist()
    except Exception as exc:
        state.update(status='deployment error; artifacts retained', error_type=type(exc).__name__, error=str(exc))
        persist()
        raise
    finally:
        # Signals apply only to process groups created and still owned here.
        for name, proc in reversed(procs):
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=15)
        state['services_released_at'] = time.time()
        persist()


if __name__ == '__main__':
    main()
