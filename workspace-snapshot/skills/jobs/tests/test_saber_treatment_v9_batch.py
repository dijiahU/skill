"""Pure mock checks for batch ownership, admission, and judge gating."""

import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


JOBS = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, JOBS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


batch = load('batch', 'run_saber_treatment_v9_full_batch.py')
entry = load('entry', 'saber_treatment_v9_container_entry.py')


class BatchTests(unittest.TestCase):
    def test_sandbox_labels_and_name_only(self):
        original = ['docker', 'run', '-d', '--rm', '--name', 'osbench-a0123456',
                    '--network=none', '--memory=256m', 'osbench-sandbox:latest']
        tagged = entry.tag_sandbox_command(original, batch.BATCH, 'deepseek_flash')
        self.assertIn('rick-saber.batch=' + batch.BATCH, tagged)
        self.assertIn('rick-saber.model=deepseek_flash', tagged)
        self.assertIn('rick-saber-' + batch.BATCH + '-deepseek-flash-osbench-a0123456', tagged)
        self.assertEqual(tagged[-3:], original[-3:])
        self.assertEqual(original[original.index('--name') + 1], 'osbench-a0123456')

    def test_never_relabel_idle_or_other_containers(self):
        for name in ('rick-saber-idle-a01234567890-g0-runner', 'shared-service', 'osbench-bad'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                entry.tag_sandbox_command(['docker', 'run', '--name', name], batch.BATCH, 'glm')

    def test_reject_foreign_batch(self):
        with self.assertRaises(ValueError):
            entry.tag_sandbox_command(['docker', 'run', '--name', 'osbench-a0123456'], 'foreign', 'glm')

    def test_non_creation_command_unchanged(self):
        command = ['docker', 'exec', 'owned-id', 'cat', 'Makefile']
        self.assertIs(entry.tag_sandbox_command(command, batch.BATCH, 'glm'), command)

    def test_local_lifecycle_uses_admission(self):
        with patch.object(batch.subprocess, 'Popen') as run:
            run.return_value.wait.return_value = 0
            batch.launch_managed(['--run-model', 'mistral'], [0, 1])
            argv = run.call_args.args[0]
        self.assertEqual(argv[:5], [str(batch.ROOT / 'bin/gpu-idle'), 'run', '--gpus', '0,1', '--timeout'])
        self.assertIn('--run-model', argv)
        self.assertIn('--cleanup-approved', argv)

    def test_remote_api_does_not_reserve_gpu(self):
        with patch.object(batch.subprocess, 'Popen') as run:
            run.return_value.wait.return_value = 0
            batch.launch_managed(['--run-model', 'deepseek_pro'], [])
            argv = run.call_args.args[0]
        self.assertNotIn('run', argv)
        self.assertNotIn('--gpus', argv)

    def test_runner_mounts_frozen_sources_and_new_raw(self):
        life = MagicMock()
        spec = {'key': 'glm', 'slug': 'new-slug'}
        endpoint = {'config': str(batch.FROZEN / 'configs/glm-0.json')}
        with patch.dict(os.environ, {'POD_USER_ROOT': '/2024233123',
            'HOST_USER_ROOT': '/mnt/inaisfs/user-fs/2024233123', 'DOCKER_HOST': 'tcp://node:2375'}):
            batch.docker_runner(life, spec, 'worker-00', endpoint, ['--skip-preflight'])
        argv = life.spawn.call_args.args[1]
        self.assertIn('rick-saber.batch=' + batch.BATCH, argv)
        self.assertIn('rick-saber.model=glm', argv)
        self.assertNotIn('--overwrite', argv)
        self.assertFalse(any('SABER_IDLE_SESSION=' in item for item in argv))
        self.assertTrue(any('frozen/saber,dst=/workspace/saber,readonly' in item for item in argv))
        self.assertTrue(any('/raw,dst=/workspace/saber/results' in item for item in argv))
        self.assertFalse(any('tmpfs' in item for item in argv))

    def test_judge_requires_validated_exit_and_both_gpus(self):
        for passed, stage, devices in [(False, 'judge_queued', '0,1'),
                                       (True, 'treatment', '0,1'),
                                       (True, 'judge_queued', '1')]:
            payloads = [json.dumps({'passed': passed, 'failures': []}), json.dumps({'stage': stage})]
            with self.subTest(stage=stage, passed=passed, devices=devices):
                with patch.object(batch, 'check_frozen'), patch.object(Path, 'read_text', side_effect=payloads):
                    with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': devices}), self.assertRaises(RuntimeError):
                        batch.run_judge({'models': []})

    def test_cleanup_refuses_mismatched_prefix(self):
        inspect = MagicMock(returncode=0, stdout=json.dumps([{
            'Name': '/shared-service', 'Config': {'Labels': {
                'rick-saber.batch': batch.BATCH, 'rick-saber.model': 'glm'}}}]))
        with patch.object(batch.subprocess, 'check_output', return_value='owned-id\n'):
            with patch.object(batch.subprocess, 'run', return_value=inspect) as run:
                with self.assertRaises(RuntimeError):
                    batch.cleanup_containers('glm')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:2], ['docker', 'inspect'])

    def test_cleanup_requires_both_labels(self):
        inspect = MagicMock(returncode=0, stdout=json.dumps([{
            'Name': '/rick-saber-' + batch.BATCH + '-glm-worker-00',
            'Config': {'Labels': {'rick-saber.batch': batch.BATCH, 'rick-saber.model': 'other'}}}]))
        with patch.object(batch.subprocess, 'check_output', return_value='owned-id\n'):
            with patch.object(batch.subprocess, 'run', return_value=inspect) as run:
                with self.assertRaises(RuntimeError):
                    batch.cleanup_containers('glm')
        self.assertEqual(run.call_count, 1)

    def test_cleanup_is_scoped_to_exact_id(self):
        inspect = MagicMock(returncode=0, stdout=json.dumps([{
            'Name': '/rick-saber-' + batch.BATCH + '-glm-worker-00',
            'Config': {'Labels': {'rick-saber.batch': batch.BATCH, 'rick-saber.model': 'glm'}}}]))
        with patch.object(batch.subprocess, 'check_output', return_value='owned-id\n'):
            with patch.object(batch.subprocess, 'run', return_value=inspect) as run, patch.object(batch, 'event'):
                batch.cleanup_containers('glm')
        self.assertEqual(run.call_args.args[0], ['docker', 'rm', '-f', 'owned-id'])


if __name__ == '__main__':
    unittest.main()

