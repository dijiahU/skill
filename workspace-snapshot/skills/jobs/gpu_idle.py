#!/usr/bin/env python3
"""Per-GPU preemptible Qwen SABER load; foreground jobs use gpu-idle run."""
import argparse
import contextlib
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

ROOT = Path('/2024233123/skills')
STATE = ROOT / 'logs/gpu-idle'
SABER = ROOT / 'projects/skill/saber'
BUNDLE = ROOT / 'projects/skill/agent-safety-orchestrator/agent-safety-orchestrator'
VENV = ROOT / 'envs/qwen35-vllm'
MODEL_ID = 'Qwen/Qwen3.8-27B-FP8'
MODEL = ROOT / 'models/modelscope' / MODEL_ID
IMAGE = 'saber-codex-runner:0.149.1'
SLUG = 'codex_qwen38_27b_idle'
LABEL = 'skilldistill.idle.session'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
STOP = threading.Event()


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def save(path, data):
    """Atomically replace only controller-owned metadata; never unlink files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + '.pending')
    staging.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(staging, path)


def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def event(message):
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'events.log').open('a') as handle:
        handle.write(f'{now()} {message}\n')
    print(f'{now()} {message}', flush=True)


def birth(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, IndexError):
        return None


def alive(owner):
    return bool(owner and owner.get('birth') and birth(owner.get('pid')) == owner['birth'])


def identity(pid):
    return {'pid': pid, 'birth': birth(pid)}


@contextlib.contextmanager
def lock(path, nonblocking=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield handle


def command(argv, timeout=10, check=True):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=check)


def gpu_snapshot():
    rows = command(['nvidia-smi', '--query-gpu=index,uuid,memory.used,utilization.gpu',
                    '--format=csv,noheader,nounits']).stdout.splitlines()
    cards = {}
    for row in rows:
        index, device, memory, utilization = [v.strip() for v in row.split(',')]
        cards[int(index)] = {'uuid': device, 'memory_mib': int(memory),
                            'utilization': int(utilization), 'pids': []}
    apps = command(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                    '--format=csv,noheader,nounits']).stdout.splitlines()
    for row in apps:
        device, pid = [v.strip() for v in row.split(',')]
        for card in cards.values():
            if card['uuid'] == device:
                card['pids'].append(int(pid))
    return cards


def reservations():
    reserved = set()
    for path in (STATE / 'requests').glob('*.json'):
        request = read(path)
        if request.get('active') and (alive(request.get('owner')) or alive(request.get('child'))):
            reserved.update(request['gpus'])
    return reserved


def external_servers(own_groups, cards):
    """Best-effort early detection; only the foreground wrapper guarantees handoff."""
    busy = set()
    rows = command(['ps', '-eo', 'pid=,pgid=,args=']).stdout.splitlines()
    for row in rows:
        parts = row.split(None, 2)
        if len(parts) != 3:
            continue
        pid, pgid, args = parts
        argv = args.split()
        executable = Path(argv[0]).name if argv else ''
        direct = 'python' in executable or executable in ('vllm', 'torchrun')
        if not direct or not (('vllm' in args and 'serve' in argv) or executable == 'torchrun'):
            continue
        if int(pgid) in own_groups:
            continue
        try:
            env = dict(item.split(b'=', 1) for item in
                       Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if b'=' in item)
            visible = env.get(b'CUDA_VISIBLE_DEVICES', b'0,1').decode()
        except (OSError, ValueError):
            busy.update(cards)
            continue
        for item in visible.split(','):
            item = item.strip()
            if item.isdigit() and int(item) in cards:
                busy.add(int(item))
            elif item.startswith('GPU-'):
                busy.update(gpu for gpu, card in cards.items() if card['uuid'].startswith(item))
    return busy


def idle_allowed(card, reserved, foreign):
    return not reserved and not foreign and card['memory_mib'] <= 2048 and not card['pids']


def healthy(port):
    try:
        with HTTP.open(f'http://127.0.0.1:{port}/health', timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def host_path(path):
    return str(Path(os.environ['HOST_USER_ROOT']) /
               Path(path).resolve().relative_to(os.environ['POD_USER_ROOT']))


def spawn(argv, log=None, env=None):
    with (log.open('a') if log else open(os.devnull, 'w')) as output:
        process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    process.idle_identity = identity(process.pid)
    return process


def stop_groups(processes):
    """Signal only groups we created, checking PID birth to prevent reuse mistakes."""
    def send(process, sig):
        current = birth(process.pid)
        if current and current != process.idle_identity['birth']:
            raise RuntimeError(f'PID reused: {process.pid}; refusing to signal')
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, sig)
    for process in processes:
        send(process, signal.SIGTERM)
    time.sleep(2)
    for process in processes:
        send(process, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)


def owned_containers(token, role=None):
    args = ['docker', 'ps', '-q', '--no-trunc', '--filter', f'label={LABEL}={token}']
    if role:
        args += ['--filter', f'label=skilldistill.idle.role={role}']
    ids = command(args).stdout.split()
    if not ids:
        return []
    containers = json.loads(command(['docker', 'inspect', *ids]).stdout)
    return [c['Id'] for c in containers
            if c['Config'].get('Labels', {}).get(LABEL) == token
            and c['Name'].startswith(f'/rick-saber-idle-{token}-')]


def stop_containers(token, role=None):
    ids = owned_containers(token, role)
    if ids:
        command(['docker', 'kill', *ids], timeout=20, check=False)


class Slot:
    def __init__(self, gpu):
        self.gpu = gpu
        self.token = uuid.uuid4().hex[:12] + f'-g{gpu}'
        self.directory = STATE / 'sessions' / self.token
        self.directory.mkdir(parents=True)
        self.api = 18140 + gpu * 2
        self.proxy_port = self.api + 1
        self.processes = []
        self.workers = {}
        self.cycles = [0] * 4
        self.stage = 'loading'
        self.started = time.monotonic()
        self.nvml_pids = set()
        self.next_worker = [0.0] * 4
        self.last_health = 0
        self.health_failures = 0
        self.server = None
        self.proxy = None

    def launch(self):
        for port in (self.api, self.proxy_port):
            with socket.socket() as check:
                check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                check.bind(('0.0.0.0', port))
        config = {'max_steps': 30, 'models': {SLUG: {
            'id': MODEL_ID, 'type': 'codex-native',
            'base_url': f"http://{os.environ['SABER_IDLE_POD_IP']}:{self.proxy_port}/v1",
            'copy_codex_auth': False, 'preload_skill_references': False}}}
        save(self.directory / 'config.json', config)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(self.gpu),
                   SAFETENSORS_FAST_GPU='1', VLLM_WORKER_MULTIPROC_METHOD='spawn',
                   VLLM_NO_USAGE_STATS='1', VLLM_FORCE_NATIVE_GDN='1',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        self.server = spawn(['nice', '-n', '10', str(VENV / 'bin/vllm'), 'serve', str(MODEL),
            '--served-model-name', MODEL_ID, '--host', '0.0.0.0', '--port', str(self.api),
            '--tensor-parallel-size', '1', '--max-model-len', '32768', '--max-num-seqs', '4',
            '--gpu-memory-utilization', '0.80', '--enable-auto-tool-choice',
            '--tool-call-parser', 'qwen3_xml', '--reasoning-parser', 'qwen3',
            '--language-model-only'], self.directory / 'vllm.log', env)
        self.processes.append(self.server)
        event(f'gpu={self.gpu} loading session={self.token} pid={self.server.pid}')

    def runner(self, worker, preflight=False):
        suffix = 'preflight' if preflight else f'w{worker}-c{self.cycles[worker]}'
        args = ['docker', 'run', '--rm', '--runtime', 'runc', '--log-driver', 'none',
                '--name', f'rick-saber-idle-{self.token}-{suffix}',
                '--label', f'{LABEL}={self.token}', '--label', 'skilldistill.idle.role=runner',
                '--env', f'SABER_IDLE_SESSION={self.token}',
                '--env', f"DOCKER_HOST={os.environ['DOCKER_HOST']}",
                '--env', 'DOCKER_API_VERSION=1.43', '--env', 'SABER_DOCKER_RUNTIME=runc',
                '--tmpfs', '/workspace/saber/results:rw,nosuid,nodev,size=1g']
        mounts = [(self.directory / 'config.json', '/run/secrets/saber-config.json'),
                  (SABER / 'harness_adapters/codex_native_adapter.py',
                   '/workspace/saber/harness_adapters/codex_native_adapter.py'),
                  (SABER / 'sandbox_shell.py', '/workspace/saber/sandbox_shell.py'),
                  (BUNDLE, '/workspace/agent-safety-orchestrator/agent-safety-orchestrator')]
        if not preflight:
            part = (worker + self.gpu * 4 + self.cycles[worker] * 4) % 8
            mounts.append((ROOT / f'jobs/saber_glm47_baseline_716_subsets/part-{part:02d}.json',
                           '/run/secrets/saber-subset.json'))
        for source, destination in mounts:
            args += ['--mount', f'type=bind,src={host_path(source)},dst={destination},readonly']
        args += [IMAGE, 'python3', 'run_harness.py', '--harness', 'codex-native',
                 '--config', '/run/secrets/saber-config.json', '--model', SLUG,
                 '--skill-mode', 'safety-orchestrator', '--safety-orchestrator',
                 '/workspace/agent-safety-orchestrator/agent-safety-orchestrator']
        args += (['--preflight-only', 'A_fs_001'] if preflight else
                 ['--skip-preflight', '--subset', '/run/secrets/saber-subset.json'])
        process = spawn(args, self.directory / 'preflight.log' if preflight else None)
        self.processes.append(process)
        return process

    def step(self, card):
        if self.server.poll() is not None:
            raise RuntimeError(f'vllm exited {self.server.returncode}')
        apps = set(card['pids'])
        if not self.nvml_pids and len(apps) == 1:
            # Host GPU PIDs differ from Pod PIDs. Capture the sole process after
            # empty-card launch; external launch detection is an additional guard.
            self.nvml_pids = apps
        if len(apps) > 1 or (self.nvml_pids and apps - self.nvml_pids):
            raise RuntimeError('another CUDA process appeared; yielding GPU')
        if self.stage == 'loading' and healthy(self.api):
            self.proxy = spawn([str(VENV / 'bin/python'), str(ROOT / 'bin/vllm_responses_compat_proxy.py'),
                '--host', '0.0.0.0', '--port', str(self.proxy_port),
                '--upstream', f'http://127.0.0.1:{self.api}', '--emulate-stream', '--temperature', '0'],
                self.directory / 'proxy.log')
            self.processes.append(self.proxy)
            self.stage = 'proxy'
        if self.proxy and self.proxy.poll() is not None:
            raise RuntimeError('proxy exited')
        if self.stage == 'proxy' and healthy(self.proxy_port):
            self.preflight = self.runner(0, preflight=True)
            self.stage = 'preflight'
        if self.stage == 'preflight' and self.preflight.poll() is not None:
            self.processes.remove(self.preflight)
            if self.preflight.returncode:
                raise RuntimeError('preflight failed; see preflight.log')
            self.stage = 'running'
            event(f'gpu={self.gpu} ready workers=4 session={self.token}')
        if self.stage != 'running' and time.monotonic() - self.started > 900:
            raise RuntimeError('startup exceeded 900 seconds')
        if self.stage == 'running':
            if time.monotonic() - self.last_health > 15:
                self.last_health = time.monotonic()
                self.health_failures = 0 if healthy(self.api) and healthy(self.proxy_port) else self.health_failures + 1
                if self.health_failures >= 3:
                    raise RuntimeError('three consecutive failed health checks')
            for worker in range(4):
                process = self.workers.get(worker)
                if process and process.poll() is not None:
                    event(f'gpu={self.gpu} worker={worker} cycle={self.cycles[worker]} exit={process.returncode}')
                    self.cycles[worker] += 1
                    self.next_worker[worker] = time.monotonic() + (15 if process.returncode else 0)
                    self.workers.pop(worker)
                    self.processes.remove(process)
                if worker not in self.workers and time.monotonic() >= self.next_worker[worker]:
                    self.workers[worker] = self.runner(worker)

    def stop(self):
        self.stage = 'stopping'
        stop_groups(self.processes)
        for role in ('runner', 'sandbox', None):
            stop_containers(self.token, role)
        if owned_containers(self.token):
            raise RuntimeError(f'containers remain for {self.token}')
        self.stage = 'stopped'
        event(f'gpu={self.gpu} released session={self.token}')

    def status(self):
        return {'session': self.token, 'stage': self.stage,
                'groups': [p.pid for p in self.processes], 'cycles': self.cycles,
                'workers': len(self.workers), 'log_dir': str(self.directory)}


def daemon_status(slots, cards, reserved, foreign, running=True):
    return {'updated': now(), 'heartbeat': time.time(), 'owner': identity(os.getpid()),
            'running': running, 'gpus': cards, 'reserved': sorted(reserved),
            'external_servers': sorted(foreign),
            'slots': {str(gpu): slot.status() for gpu, slot in slots.items()}}


def serve(args):
    STATE.mkdir(parents=True, exist_ok=True)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    with lock(ROOT / 'jobs/.saber-qwen38-27b-burnin-forever.lock', True):
        slots, cards, reserved, foreign = {}, {}, set(), set()
        idle_since = {gpu: time.monotonic() for gpu in (0, 1)}
        old = read(STATE / 'status.json')
        if old.get('slots'):
            raise RuntimeError('Previous controller has recorded slots; inspect before restarting')
        event(f'controller_start pid={os.getpid()} idle_seconds={args.idle_seconds}')
        try:
            while not STOP.is_set():
                try:
                    cards = gpu_snapshot()
                    own = {p.pid for slot in slots.values() for p in slot.processes}
                    foreign = external_servers(own, cards)
                    with lock(STATE / 'allocation.lock'):
                        reserved = reservations()
                        for gpu in (0, 1):
                            card = cards[gpu]
                            busy = gpu in reserved or gpu in foreign
                            if gpu in slots:
                                slot = slots[gpu]
                                try:
                                    if busy or slot.stage == 'stopping':
                                        raise RuntimeError('foreground needs GPU')
                                    slot.step(card)
                                except Exception as exc:
                                    event(f'gpu={gpu} stopping reason={exc}')
                                    slot.stop()
                                    slots.pop(gpu)
                                    idle_since[gpu] = time.monotonic()
                            elif not idle_allowed(card, gpu in reserved, gpu in foreign):
                                idle_since[gpu] = time.monotonic()
                            elif time.monotonic() - idle_since[gpu] >= args.idle_seconds:
                                slot = Slot(gpu)
                                slots[gpu] = slot
                                slot.launch()
                        save(STATE / 'status.json', daemon_status(slots, cards, reserved, foreign))
                except Exception as exc:
                    event(f'controller_check_error={exc}')
                    for gpu, slot in list(slots.items()):
                        try:
                            slot.stop()
                            slots.pop(gpu)
                        except Exception as stop_error:
                            event(f'gpu={gpu} cleanup_retry={stop_error}')
                        idle_since[gpu] = time.monotonic()
                    save(STATE / 'status.json', daemon_status(slots, cards, reserved, foreign))
                    STOP.wait(15)
                STOP.wait(2)
        finally:
            for gpu, slot in list(slots.items()):
                try:
                    slot.stop()
                    slots.pop(gpu)
                except Exception as exc:
                    event(f'gpu={gpu} cleanup_incomplete={exc}')
            save(STATE / 'status.json', daemon_status(slots, cards, reserved, foreign, False))
            event('controller_stopped')


def run_foreground(args):
    gpus = sorted(set(int(v) for v in args.gpus.split(',')))
    if not gpus or any(v not in (0, 1) for v in gpus):
        raise ValueError('--gpus must be 0, 1, or 0,1')
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not argv:
        raise ValueError('command required after --')
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    deadline = time.monotonic() + args.timeout
    request_path = STATE / 'requests' / (uuid.uuid4().hex + '.json')
    request = {'active': True, 'owner': identity(os.getpid()), 'gpus': gpus, 'created': now()}
    child = None
    with contextlib.ExitStack() as stack:
        for gpu in gpus:
            while True:
                try:
                    stack.enter_context(lock(STATE / f'foreground-gpu{gpu}.lock', True))
                    break
                except BlockingIOError:
                    if STOP.is_set() or time.monotonic() > deadline:
                        raise TimeoutError('waiting for another foreground reservation')
                    STOP.wait(1)
        with lock(STATE / 'allocation.lock'):
            save(request_path, request)
        event(f'foreground_request gpus={gpus} pid={os.getpid()}')
        try:
            while not STOP.is_set() and time.monotonic() < deadline:
                with lock(STATE / 'allocation.lock'):
                    cards = gpu_snapshot()
                    status = read(STATE / 'status.json')
                    active = status.get('slots', {})
                    foreign = external_servers(set(), cards)
                    if all(str(gpu) not in active and
                           idle_allowed(cards[gpu], False, gpu in foreign) for gpu in gpus):
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=','.join(map(str, gpus)))
                        child = subprocess.Popen(argv, env=env, start_new_session=True)
                        child.idle_identity = identity(child.pid)
                        request['child'] = child.idle_identity
                        save(request_path, request)
                        event(f'foreground_start gpus={gpus} child={child.pid}')
                        break
                STOP.wait(1)
            if child is None:
                raise TimeoutError('GPU handoff timed out or cancelled; command not launched')
            while child.poll() is None and not STOP.wait(1):
                pass
            if STOP.is_set() and child.poll() is None:
                stop_groups([child])
            return child.wait()
        finally:
            request['active'] = False
            request['released'] = now()
            save(request_path, request)
            event(f'foreground_release gpus={gpus}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    for name in ('start', 'serve'):
        subs.add_parser(name).add_argument('--idle-seconds', type=float, default=30)
    subs.add_parser('status')
    subs.add_parser('stop')
    run = subs.add_parser('run')
    run.add_argument('--gpus', required=True)
    run.add_argument('--timeout', type=float, default=600)
    run.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'status':
        state = read(STATE / 'status.json')
        state['controller_alive'] = alive(state.get('owner'))
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif args.action == 'run':
        return run_foreground(args)
    elif args.action == 'stop':
        state = read(STATE / 'status.json')
        if alive(state.get('owner')):
            os.kill(state['owner']['pid'], signal.SIGTERM)
            for _ in range(60):
                if not alive(state['owner']):
                    if read(STATE / 'status.json').get('slots'):
                        raise RuntimeError('Controller exited with pending cleanup; inspect status')
                    print('Idle controller stopped.')
                    return 0
                time.sleep(1)
            raise TimeoutError('Controller cleanup pending; inspect status and events.log')
        print('Idle controller is not running.')
    elif args.action == 'start':
        state = read(STATE / 'status.json')
        if alive(state.get('owner')):
            print(f"Already running: {state['owner']['pid']}")
            return 0
        ip = command(['hostname', '-I']).stdout.split()[0]
        env = dict(os.environ, SABER_IDLE_POD_IP=ip)
        STATE.mkdir(parents=True, exist_ok=True)
        proc = spawn([sys.executable, __file__, 'serve', '--idle-seconds', str(args.idle_seconds)],
                     STATE / 'controller.log', env)
        for _ in range(20):
            state = read(STATE / 'status.json')
            if state.get('owner', {}).get('pid') == proc.pid and state.get('running'):
                print(f'Idle controller started: pid={proc.pid}, status={STATE / "status.json"}')
                return 0
            if proc.poll() is not None:
                raise RuntimeError(f'Start failed; inspect {STATE / "controller.log"}')
            time.sleep(1)
        raise TimeoutError('Startup not acknowledged; inspect controller.log')
    else:
        return serve(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'gpu-idle: {error}', file=sys.stderr)
        sys.exit(1)
