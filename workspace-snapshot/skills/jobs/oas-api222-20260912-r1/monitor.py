"""Read scoped Docker stats with a bounded sample; never mutate resources."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

JOB = Path(__file__).resolve().parent
DOCKER = '/srv/benchmark/skills/bin/docker'
LABEL = 'skilldistill.oas.api_run=oas-api222-20260912-r1'
LAST_CPU = None


def snapshot(stage=None):
    global LAST_CPU
    row = {'time': time.time(), 'stage': stage, 'loadavg': list(os.getloadavg()),
           'pod_memory_bytes': int(Path('/sys/fs/cgroup/memory.current').read_text())}
    cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    if LAST_CPU:
        delta = [b-a for a,b in zip(LAST_CPU,cpu)]
        row['node_cpu_busy_percent'] = round(100*(sum(delta)-delta[3]-delta[4])/max(1,sum(delta)),2)
    LAST_CPU = cpu
    try:
        args = [DOCKER, 'ps', '--filter', 'label=' + LABEL]
        if stage:
            args += ['--filter', 'label=skilldistill.oas.stage=' + stage]
        listed = subprocess.run(args + ['--format', '{{.ID}}'], capture_output=True, text=True, timeout=15, check=True)
        ids = listed.stdout.split()
        row['running_containers'] = len(ids)
        sampled = list(dict.fromkeys(ids[:8] + ids[-8:]))
        endpoint = os.environ['DOCKER_HOST'].replace('tcp://','http://',1)
        def stats(container):
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(endpoint + '/v1.43/containers/' + container + '/stats?stream=false&one-shot=true', timeout=5) as response:
                    item = json.load(response)
                memory = item.get('memory_stats', {})
                return {'id':container, 'memory_bytes':memory.get('usage'), 'memory_limit_bytes':memory.get('limit'),
                        'pids':item.get('pids_stats',{}).get('current'),
                        'cpu_total_ns':item.get('cpu_stats',{}).get('cpu_usage',{}).get('total_usage')}
            except Exception as exc:
                return {'id':container, 'error':type(exc).__name__}
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            row['container_sample'] = list(pool.map(stats,sampled))
    except Exception as exc:
        row['monitor_error'] = type(exc).__name__
    with (JOB / 'resources.jsonl').open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    return row


if __name__ == '__main__':
    print(json.dumps(snapshot()))
