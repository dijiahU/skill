"""Serialize OAS container admission without modifying the shared bridge."""
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time

JOB = Path(__file__).resolve().parent
REAL = '/srv/benchmark/skills/bin/docker'
PREFIX = 'rick-oas-api222-20260912-r1-'
MAX_AGENTS = 96
RESERVE_ADDRESSES = 32


def capacity(network):
    configs = network.get('IPAM', {}).get('Config', [])
    subnet = next(ipaddress.ip_network(c.get('IPRange') or c['Subnet']) for c in configs
                  if ':' not in c['Subnet'])
    usable = max(0, subnet.num_addresses - 3)
    containers = network.get('Containers', {})
    used = len(containers)
    owned = sum(c.get('Name', '').startswith(PREFIX) for c in containers.values())
    return {'owned_agents': owned, 'used_addresses': used, 'usable_addresses': usable,
            'free_addresses': usable - used,
            'can_start': owned < MAX_AGENTS and usable - used > RESERVE_ADDRESSES}


def run_bounded(args, grader=False):
    started = time.monotonic()
    last_report = 0
    while time.monotonic() - started < 1800:
        stage = os.environ.get('OAS_STAGE', 'unknown')
        if (JOB / ('stop-' + stage + '.json')).exists():
            raise RuntimeError('Stage admission stopped before allocation')
        if grader:
            for index in range(8):
                slot = (JOB / ('grader-slot-' + str(index) + '.lock')).open('a')
                try:
                    fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    slot.close()
                    continue
                with slot:
                    return subprocess.run([REAL, *args], check=False).returncode
        else:
            with (JOB / 'container-admission.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                result = subprocess.run([REAL, 'network', 'inspect', 'bridge'],
                                        capture_output=True, text=True, timeout=20, check=True)
                state = capacity(json.loads(result.stdout)[0])
                if state['can_start']:
                    # Detached docker run returns after attaching its IP. Keep
                    # admission serialized until then to avoid count races.
                    return subprocess.run([REAL, *args], check=False).returncode
                if time.monotonic() - last_report > 30:
                    with (JOB / 'capacity-waits.jsonl').open('a') as stream:
                        stream.write(json.dumps({'stage': stage, 'time': time.time(), **state}) + '\n')
                    last_report = time.monotonic()
        time.sleep(2)
    raise TimeoutError('No safe OAS container capacity after 1800 seconds')
