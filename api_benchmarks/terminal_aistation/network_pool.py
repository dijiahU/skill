"""Persistent small private subnets; no daemon configuration or network cleanup."""
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(os.environ.get('TERMINAL_BENCH_NETWORK_STATE_DIR', '/srv/benchmark/skills/jobs/terminal-bench-repair-20260910-r1'))
# Reserved benchmarking range as a public example; configure your own pool.
POOL = ipaddress.ip_network(os.environ.get('TERMINAL_BENCH_NETWORK_POOL', '198.18.0.0/16'))


def host_routes(path):
    nets = []
    for line in path.read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[7] == '00000000':
            continue
        addr = str(ipaddress.ip_address(bytes.fromhex(fields[1])[::-1]))
        mask = str(ipaddress.ip_address(bytes.fromhex(fields[7])[::-1]))
        nets.append(ipaddress.ip_network(addr + '/' + mask, strict=False))
    return nets


def reserve(session):
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'subnets.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = ROOT / 'subnets.json'
        ledger = json.loads(path.read_text()) if path.exists() else {}
        if session in ledger:
            return ledger[session]
        ids = subprocess.check_output(['docker','network','ls','-q'], text=True).split()
        networks = json.loads(subprocess.check_output(['docker','network','inspect',*ids], text=True)) if ids else []
        occupied = host_routes(ROOT / 'host-routes.txt')
        occupied += [ipaddress.ip_network(item['Subnet']) for net in networks
                     for item in net.get('IPAM',{}).get('Config',[]) if item.get('Subnet')]
        occupied += [ipaddress.ip_network(value) for value in ledger.values()]
        for subnet in POOL.subnets(new_prefix=28):
            if any(subnet.version == other.version and subnet.overlaps(other) for other in occupied):
                continue
            ledger[session] = str(subnet)
            path.write_text(json.dumps(ledger, indent=2))
            return str(subnet)
        raise RuntimeError('Project small-subnet pool exhausted; no cleanup performed')
