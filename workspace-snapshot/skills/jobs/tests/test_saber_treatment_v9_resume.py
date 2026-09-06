"""Mock-only regression checks for six-model recovery; no real resource changes."""

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


JOBS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(JOBS))
spec = importlib.util.spec_from_file_location('v9_resume_tests_target', JOBS / 'run_saber_treatment_v9_resume.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


def manifest():
    return {'task_ids': ['task'], 'models': [
        {'key': key, 'gpus': [] if key == 'deepseek_pro' else [0, 1], 'result_slug': key}
        for key in ['mistral', *resume.REMAINING]]}


class RecoveryTests(unittest.TestCase):
    def test_gpu_lifecycle_is_foreground_admitted(self):
        argv = resume.managed_command(['--run-model', 'minimax'], [0, 1])
        self.assertEqual(argv[:5], [str(resume.ROOT / 'bin/gpu-idle'), 'run', '--gpus', '0,1', '--timeout'])
        self.assertIn(str(resume.RECOVERY / 'run_saber_treatment_v9_resume.py'), argv)
        self.assertIn('--cleanup-approved', argv)

    def test_remote_model_has_no_gpu_reservation(self):
        argv = resume.managed_command(['--run-model', 'deepseek_pro'], [])
        self.assertNotIn('--gpus', argv)

    def test_existing_remaining_artifacts_refused(self):
        with patch.object(Path, 'rglob', return_value=iter([Path('existing.json')])):
            with self.assertRaisesRegex(RuntimeError, 'already has artifacts'):
                resume.require_unstarted(manifest())

    def test_existing_containers_refused_without_cleanup(self):
        with patch.object(Path, 'rglob', return_value=[]):
            with patch.object(resume.subprocess, 'check_output', return_value='existing-container'):
                with self.assertRaisesRegex(RuntimeError, 'containers still exist'):
                    resume.require_unstarted(manifest())

    def test_inventory_mismatch_refused(self):
        data = manifest()
        data['models'] = data['models'][1:]
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            resume.require_unstarted(data)

    def test_technical_failure_does_not_skip_later_models_or_start_judge(self):
        reports = lambda item, ids: {'passed': item['key'] != 'mistral',
                                    'totals': {'technical_fail': 34 if item['key'] == 'mistral' else 0}}
        with patch.object(resume, 'check_inputs'), patch.object(resume, 'status'):
            with patch.object(resume, 'event'), patch.object(resume, 'cleanup_model'):
                with patch.object(resume.batch, 'cleanup_containers'), patch.object(resume.batch, 'save'):
                    with patch.object(resume.batch, 'validate', side_effect=reports):
                        with patch.object(resume, 'launch', side_effect=[1, 0, 0, 0, 0, 0]) as launch:
                            code = resume.run_remaining(manifest(), {'mistral_validation': {'technical_fail': 34}})
        self.assertEqual(code, 1)
        self.assertEqual([call.args[0] for call in launch.call_args_list],
                         [['--run-model', key] for key in resume.REMAINING])

    def test_unsafe_cleanup_blocks_next_launch(self):
        with patch.object(resume, 'check_inputs'), patch.object(resume, 'status'), patch.object(resume, 'event'):
            with patch.object(resume, 'launch', return_value=0) as launch:
                with patch.object(resume, 'cleanup_model', side_effect=RuntimeError('unsafe')):
                    with self.assertRaisesRegex(RuntimeError, 'unsafe'):
                        resume.run_remaining(manifest(), {'mistral_validation': {'technical_fail': 34}})
        self.assertEqual(launch.call_count, 1)

    def test_mistral_fingerprint_change_refused(self):
        digest = hashlib.sha256(b'fixed').hexdigest()
        hashes = {name: digest for name in resume.OVERLAY_FILES + ['checkpoint.json']}
        checkpoint = {'mistral_result_slug': 'mistral', 'mistral_fingerprint': {'A.json': 'before'}}
        with patch.object(resume.batch, 'check_frozen'), patch.object(Path, 'read_bytes', return_value=b'fixed'):
            with patch.object(resume, 'read', side_effect=[hashes, checkpoint]):
                with patch.object(resume.batch, 'fingerprint', return_value={'A.json': 'changed'}):
                    with self.assertRaisesRegex(RuntimeError, 'Mistral results changed'):
                        resume.check_inputs()

    def test_overlay_change_refused(self):
        with patch.object(resume.batch, 'check_frozen'), patch.object(Path, 'read_bytes', return_value=b'changed'):
            with patch.object(resume, 'read', return_value={}):
                with self.assertRaisesRegex(RuntimeError, 'overlay or checkpoint changed'):
                    resume.check_inputs()

    def test_spawn_records_identity_and_does_not_inherit_idle_flags(self):
        with patch.object(Path, 'mkdir'), patch.object(Path, 'open'):
            with patch.object(resume.subprocess, 'Popen') as popen, patch.object(resume.batch, 'save') as save:
                with patch.object(resume.ownership, 'capture', return_value={'pid': 123, 'birth': 456}):
                    with patch.object(resume, 'event'), patch.dict(os.environ, {'SABER_IDLE_SESSION': 'idle', 'SABER_DISCARD_RESULTS': '1'}):
                        popen.return_value.pid = 123
                        life = resume.RecoveryLifecycle('minimax')
                        life.spawn('vllm', ['python', 'vllm'])
        kwargs = popen.call_args.kwargs
        self.assertTrue(kwargs['start_new_session'])
        self.assertNotIn('SABER_IDLE_SESSION', kwargs['env'])
        self.assertNotIn('SABER_DISCARD_RESULTS', kwargs['env'])
        self.assertEqual(save.call_args.args[1][0]['identity']['birth'], 456)

    def test_capture_failure_stops_only_new_direct_child(self):
        with patch.object(Path, 'mkdir'), patch.object(Path, 'open'):
            with patch.object(resume.subprocess, 'Popen') as popen, patch.object(resume.batch, 'save'):
                with patch.object(resume.ownership, 'capture', side_effect=RuntimeError('capture failed')):
                    popen.return_value.poll.return_value = None
                    with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                        resume.RecoveryLifecycle('minimax').spawn('vllm', ['python', 'vllm'])
        popen.return_value.terminate.assert_called_once()

    def test_cleanup_only_uses_new_identity_ledger(self):
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(resume, 'read', return_value=[{'identity': {'pid': 1}}, {'identity': None}]):
                with patch.object(resume.ownership, 'cleanup') as cleanup:
                    resume.cleanup_model('minimax')
        cleanup.assert_called_once_with([{'pid': 1}], resume.BATCH, 'minimax')


if __name__ == '__main__':
    unittest.main()
