"""Own a dual-GPU DeepSeek service for the complete Judge shadow lifecycle.

Run through gpu-idle run --gpus 0,1. No Docker task containers are created.
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
from saber_v10_model_specs import MODEL_SPECS
from saber_treatment_v9_spawn_capture import capture_spawn
from saber_treatment_v9_process_ownership import cleanup


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(directory: Path, gold: Path, *, pipeline: bool = False, enable_thinking: bool = False,
        smoke_runner: Path | None = None):
    if smoke_runner is not None and pipeline:
        raise ValueError('A targeted smoke is not a full-pipeline gate')
    spec = next(item for item in MODEL_SPECS if item['key'] == 'deepseek_flash')
    if os.environ.get('CUDA_VISIBLE_DEVICES') != ','.join(map(str, spec['gpus'])):
        raise RuntimeError('Reserve both GPUs for the complete Judge lifecycle')
    directory.mkdir(parents=True, exist_ok=False)
    service = next(item for item in spec['services'] if item['argv'][1] == 'serve')
    parsed = urlsplit(service['health_url'])
    with socket.socket() as sock:
        sock.bind(('0.0.0.0', parsed.port))
    scope, model = 'v10-judge-' + directory.name, spec['key']
    env = dict(os.environ, SABER_BATCH_ID=scope, SABER_BATCH_MODEL=model, PYTHONDONTWRITEBYTECODE='1')
    env.update(service['env'])
    records, processes = [], []
    mode = 'targeted_smoke' if smoke_runner is not None else ('full_pipeline' if pipeline else 'attribution')
    status = {'status': 'starting', 'mode': mode, 'service_spec': service,
              'enable_thinking': enable_thinking, 'gold_path': str(gold), 'gold_sha256': hashlib.sha256(gold.read_bytes()).hexdigest()}
    write(directory / 'status.json', status)
    try:
        with (directory / 'model.log').open('x') as log:
            process = subprocess.Popen(service['argv'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        try:
            records.append(capture_spawn(process, scope, model))
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            raise
        write(directory / 'process-identities.json', records)
        deadline = time.monotonic() + service['ready_timeout']
        with httpx.Client(trust_env=False) as client:
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Judge model exited before readiness')
                try:
                    if client.get(service['health_url'], timeout=3).is_success:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError('Judge model readiness timeout')
                print('Judge service loading, pid=' + str(process.pid), flush=True)
                time.sleep(5)
        status['status'] = 'shadow_running'
        write(directory / 'status.json', status)
        model_id = service['argv'][service['argv'].index('--served-model-name') + 1]
        runner_name = 'run_saber_judge_full_pipeline_gate.py' if pipeline else 'run_saber_judge_shadow_gate.py'
        runner = smoke_runner or (Path(__file__).resolve().parents[1] / 'bin' / runner_name)
        command = [sys.executable, str(runner), '--base-url', service['health_url'].removesuffix('/health'),
                   '--model', model_id, '--gold', str(gold), '--output', str(directory / 'shadow-report.json')]
        if enable_thinking:
            command.append('--enable-thinking')
        status['consumer'] = {
            'argv': command,
            'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
        }
        write(directory / 'status.json', status)
        # The foreground consumer remains inside this reservation until completion.
        if hashlib.sha256(gold.read_bytes()).hexdigest() != status['gold_sha256']:
            raise RuntimeError('Gold changed while the model was loading')
        consumer = subprocess.Popen(command, env=env, start_new_session=True)
        processes.append(consumer)
        try:
            records.append(capture_spawn(consumer, scope, model))
        except BaseException:
            if consumer.poll() is None:
                consumer.terminate()
                consumer.wait(timeout=15)
            raise
        write(directory / 'process-identities.json', records)
        returncode = consumer.wait()
        status.update(status='passed' if returncode == 0 else 'shadow_failed', returncode=returncode)
        if returncode:
            raise RuntimeError('Judge shadow did not pass; inspect shadow-report.json')
    except BaseException as exc:
        status.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        try:
            write(directory / 'cleanup.json', cleanup(records, scope, model))
            for process in processes:
                process.wait(timeout=10)
            status['cleanup_safe'] = True
        except BaseException as exc:
            status.update(cleanup_safe=False, cleanup_error=str(exc))
            raise
        finally:
            write(directory / 'status.json', status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--gold', required=True, type=Path)
    parser.add_argument('--pipeline', action='store_true', help='Exercise actual judge_single, including zero-event, rules and refusal branches')
    parser.add_argument('--smoke-runner', type=Path, help='Run a targeted diagnostic consumer; cannot substitute for the full pipeline gate')
    parser.add_argument('--enable-thinking', action='store_true', help='Explicitly enable Judge model reasoning through the consumer request')
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.gold.resolve(), pipeline=args.pipeline, enable_thinking=args.enable_thinking,
        smoke_runner=args.smoke_runner.resolve() if args.smoke_runner else None)
