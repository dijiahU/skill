"""Judge lifecycle regression checks; all external effects are mocked."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('judge_service_test', Path(__file__).parents[1] / 'run_saber_v10_judge_service.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class LifecycleTests(unittest.TestCase):
    def check_run(self, code=0, changed=False, pipeline=False, enable_thinking=False, smoke_runner=None):
        server, consumer = MagicMock(pid=100), MagicMock(pid=200)
        server.poll.return_value = None
        consumer.wait.return_value = code
        client = MagicMock()
        client.__enter__.return_value.get.return_value.is_success = True
        saved = []
        def save(path, value):
            from copy import deepcopy
            saved.append((path.name, deepcopy(value)))
        with ExitStack() as stack:
            stack.enter_context(patch.dict(M.os.environ, {'CUDA_VISIBLE_DEVICES': '0,1'}))
            for target, name, kwargs in [
                (Path, 'mkdir', {}), (Path, 'open', {'return_value': MagicMock()}),
                (Path, 'read_bytes', {'side_effect': [b'gold', b'runner', b'other' if changed else b'gold']}),
                (M, 'write', {'side_effect': save}),
                (M.socket, 'socket', {'return_value': MagicMock()}),
                (M.httpx, 'Client', {'return_value': client}),
                (M, 'capture_spawn', {'side_effect': lambda process, *_: {'pid': process.pid}}),
            ]:
                stack.enter_context(patch.object(target, name, **kwargs))
            spawn = stack.enter_context(patch.object(M.subprocess, 'Popen', side_effect=[server, consumer]))
            cleanup = stack.enter_context(patch.object(M, 'cleanup', return_value={}))
            if code or changed:
                with self.assertRaises(RuntimeError):
                    M.run(Path('/memory/run'), Path('/memory/gold'), pipeline=pipeline, enable_thinking=enable_thinking, smoke_runner=smoke_runner)
            else:
                M.run(Path('/memory/run'), Path('/memory/gold'), pipeline=pipeline, enable_thinking=enable_thinking, smoke_runner=smoke_runner)
            expected = 1 if changed else 2
            self.assertEqual(spawn.call_count, expected)
            if expected == 2:
                wanted = smoke_runner.name if smoke_runner else ('run_saber_judge_full_pipeline_gate.py' if pipeline else 'run_saber_judge_shadow_gate.py')
                self.assertEqual(Path(spawn.call_args_list[1].args[0][1]).name, wanted)
            self.assertEqual(len(cleanup.call_args.args[0]), expected)
        state = [value for name, value in saved if name == 'status.json'][-1]
        self.assertEqual('--enable-thinking' in state['consumer']['argv'], enable_thinking)
        self.assertEqual(state['enable_thinking'], enable_thinking)
        self.assertTrue(state['cleanup_safe'])
        self.assertEqual(len(state['consumer']['runner_sha256']), 64)
        return state

    def test_success_captures_both_processes(self):
        self.assertEqual(self.check_run()['status'], 'passed')

    def test_failed_consumer_still_cleans_owned_processes(self):
        self.assertEqual(self.check_run(code=1)['status'], 'failed')

    def test_pipeline_selects_actual_judge_single_runner(self):
        state = self.check_run(pipeline=True)
        self.assertEqual(state['mode'], 'full_pipeline')
        self.assertEqual(state['status'], 'passed')

    def test_thinking_opt_in_reaches_consumer_and_status(self):
        self.check_run(pipeline=True, enable_thinking=True)

    def test_changed_gold_prevents_dispatch(self):
        self.assertIn('Gold changed', self.check_run(changed=True)['error'])

    def test_targeted_smoke_is_distinct_and_cleans_both_owned_processes(self):
        state = self.check_run(smoke_runner=Path('/memory/utility-smoke.py'), enable_thinking=True)
        self.assertEqual(state['mode'], 'targeted_smoke')
        self.assertTrue(state['cleanup_safe'])

    def test_smoke_cannot_claim_full_pipeline_mode(self):
        with patch.object(M.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'not a full-pipeline gate'):
                M.run(Path('/memory/run'), Path('/memory/gold'), pipeline=True,
                      smoke_runner=Path('/memory/utility-smoke.py'))
        spawn.assert_not_called()

if __name__ == '__main__': unittest.main()
