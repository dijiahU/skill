"""GPU protocol probe with no task containers or benchmark command execution.

Run the entire command under gpu-idle run with the model's exact reservation.
Own model process groups use captured birth/session identities for cleanup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

import httpx
from saber_v10_model_specs import MODEL_SPECS, SOURCE_DEPENDENCIES
from saber_treatment_v9_spawn_capture import capture_spawn
from saber_treatment_v9_process_ownership import cleanup


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def run(model, directory, extended=False, replay_rejection=None):
    spec = next(item for item in MODEL_SPECS if item['key'] == model)
    if os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(map(str, spec['gpus'])):
        raise RuntimeError('The entire probe requires its exact gpu-idle reservation')
    directory.mkdir(parents=True, exist_ok=False)
    scope = 'v10-protocol-' + directory.name
    records, children = [], []
    outcome = {'model': model, 'status': 'starting', 'gpus': spec['gpus'], 'cases': [],
               'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*SOURCE_DEPENDENCIES, Path(__file__), Path(__file__).with_name('saber_v10_protocol_cases.py'), Path(__file__).with_name('saber_v10_model_specs.py'), Path(__file__).with_name('saber_v10_stream_probe.py')]}, 'service_spec': spec}
    def status(stage, **fields):
        outcome.update(status=stage, **fields)
        write(directory / 'status.json', outcome)
        print(json.dumps({'model': model, 'stage': stage, **fields}), flush=True)
    with httpx.Client(trust_env=False, timeout=60) as client:
        try:
            for service in spec['services']:
                port = urlsplit(service['health_url']).port
                with socket.socket() as sock:
                    sock.bind(('0.0.0.0', port))
                env = dict(os.environ, SABER_BATCH_ID=scope, SABER_BATCH_MODEL=model, PYTHONDONTWRITEBYTECODE='1')
                env.update(service['env'])
                if service.get('prestart_argv'):
                    checked = subprocess.run(service['prestart_argv'], env=env, text=True, capture_output=True, timeout=120)
                    write(directory / (service['name'] + '-prestart.json'), {'returncode': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr})
                    checked.check_returncode()
                with (directory / (service['name'] + '.log')).open('x') as log:
                    process = subprocess.Popen(service['argv'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                children.append(process)
                try:
                    record = capture_spawn(process, scope, model)
                except BaseException:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
                    raise
                records.append(record)
                write(directory / 'process-identities.json', records)
                deadline = time.monotonic() + service['ready_timeout']
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Service exited: {service['name']} ({process.returncode})")
                    try:
                        if client.get(service['health_url'], timeout=3).is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Service readiness timeout: ' + service['name'])
                    status('waiting_for_service', service=service['name'], pid=process.pid)
                    time.sleep(5)
                status('service_ready', service=service['name'], pid=process.pid)
            backend = next(s for s in spec['services'] if len(s['argv']) > 1 and s['argv'][1] == 'serve')
            base = backend['health_url'].removesuffix('/health')
            model_id = backend['argv'][backend['argv'].index('--served-model-name') + 1]
            if replay_rejection is not None:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
                from saber_responses_budget import normalize_rejected_tool_history
                evidence_bytes = replay_rejection.read_bytes()
                evidence = json.loads(evidence_bytes)
                original = evidence['request']
                assert original['model'] == model_id
                normalized = normalize_rejected_tool_history(original)
                assert normalized != original, 'Rejected historical arguments were not identified'
                before = client.post(base + '/v1/saber/responses/token-count', json=original)
                after = client.post(base + '/v1/saber/responses/token-count', json=normalized)
                replay = {
                    'source': str(replay_rejection),
                    'source_sha256': hashlib.sha256(evidence_bytes).hexdigest(),
                    'before': {'status_code': before.status_code, 'body': before.text},
                    'after': {'status_code': after.status_code, 'body': after.text},
                    'generation_submitted': False,
                    'passed': before.status_code == 400 and after.status_code == 200,
                }
                write(directory / 'rejected-history-count.json', replay)
                assert replay['passed'], 'Actual historical rejection replay did not recover'
                expected_hash = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                assert after.json()['request_sha256'] == expected_hash
                outcome['historical_rejection_replay'] = replay
            for name, text in [('ascii', 'Reply with the single word OK.'), ('unicode', '请原样输出：中文路径/防火墙/🙂。不要解释。')]:
                payload = {'model': model_id, 'input': text, 'stream': False,
                           'max_output_tokens': 1024, 'store': False, 'truncation': 'disabled'}
                counter = client.post(base + '/v1/saber/responses/token-count', json=payload)
                write(directory / (name + '-count.json'), {'status_code': counter.status_code, 'body': counter.text})
                counter.raise_for_status()
                counted = counter.json()
                if model == 'mistral':
                    assert counted.get('compatibility') == {'mistral_utf8': 'saber-mistral-utf8-v10.0', 'engine_mistral_utf8': 'saber-mistral-utf8-v10.0'}, 'Actual server lacks Mistral patch markers'
                generated = client.post(base + '/v1/responses', json=payload, timeout=180)
                write(directory / (name + '-response.json'), {'status_code': generated.status_code, 'body': generated.text})
                generated.raise_for_status()
                response = generated.json()
                usage = response.get('usage') or {}
                row = {'name': name, 'counted': counted['input_tokens'], 'usage': usage,
                       'response_status': response.get('status'),
                       'count_matches': counted['input_tokens'] == usage.get('input_tokens')}
                outcome['cases'].append(row)
                status('case_complete', last_case=name)
                if not row['count_matches']:
                    raise RuntimeError('Exact rendered count disagrees with generated usage')
            # Exercise the actual configured proxy and its enabled budget guard.
            proxy = spec['endpoints'][0]['base_url']
            probe = client.post(proxy + '/responses', json=payload, timeout=180)
            write(directory / 'proxy-response.json', {'status_code': probe.status_code, 'body': probe.text})
            probe.raise_for_status()
            if extended:
                from saber_v10_protocol_cases import extended_cases
                outcome['extended_cases'] = extended_cases(client, base, proxy, model_id, directory, write)
                from saber_v10_stream_probe import stream_case
                outcome['extended_cases'].append(stream_case(client, proxy, model_id, directory, write))
            status('probe_passed')
        except BaseException as exc:
            status('failed', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            try:
                cleanup_result = cleanup(records, scope, model)
                write(directory / 'cleanup.json', cleanup_result)
                for process in children:
                    process.wait(timeout=10)
                outcome['cleanup_safe'] = True
            except BaseException as exc:
                outcome['cleanup_safe'] = False
                outcome['cleanup_error'] = str(exc)
                raise
            finally:
                write(directory / 'status.json', outcome)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=[s['key'] for s in MODEL_SPECS])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extended', action='store_true')
    parser.add_argument('--replay-rejection', type=Path)
    args = parser.parse_args()
    run(args.model, args.output.resolve(), args.extended, args.replay_rejection)
