"""Offline safety checks: no Docker writes or GPU allocations."""
import contextlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('gpu_idle', Path(__file__).parents[1] / 'gpu_idle.py')
idle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(idle)


class SchedulerTests(unittest.TestCase):
    def test_idle_requires_empty_memory_and_no_compute_process(self):
        for memory, pids, reserved, foreign, expected in [
            (1, [], False, False, True), (10000, [], False, False, False),
            (1, [22], False, False, False), (1, [], True, False, False),
            (1, [], False, True, False)]:
            self.assertEqual(idle.idle_allowed({'memory_mib': memory, 'pids': pids},
                                              reserved, foreign), expected)

    def test_pid_reuse_not_alive(self):
        with patch.object(idle, 'birth', return_value='new'):
            self.assertFalse(idle.alive({'pid': 12, 'birth': 'old'}))
            self.assertTrue(idle.alive({'pid': 12, 'birth': 'new'}))

    def test_stop_refuses_reused_pid(self):
        proc = Mock(pid=12, idle_identity={'pid': 12, 'birth': 'old'})
        with patch.object(idle, 'birth', return_value='new'), patch.object(idle.os, 'killpg') as kill:
            with self.assertRaises(RuntimeError):
                idle.stop_groups([proc])
            kill.assert_not_called()

    def test_cleanup_requires_both_label_and_name(self):
        token = 'abcdef012345-g1'
        containers = [
            {'Id': 'owned', 'Name': f'/rick-saber-idle-{token}-worker',
             'Config': {'Labels': {idle.LABEL: token}}},
            {'Id': 'other-name', 'Name': '/shared-container',
             'Config': {'Labels': {idle.LABEL: token}}},
            {'Id': 'other-label', 'Name': f'/rick-saber-idle-{token}-worker',
             'Config': {'Labels': {idle.LABEL: 'different'}}}]
        with patch.object(idle, 'command', side_effect=[
                SimpleNamespace(stdout='owned other-name other-label'),
                SimpleNamespace(stdout=json.dumps(containers))]):
            self.assertEqual(idle.owned_containers(token), ['owned'])

    def test_foreign_vllm_gpu_environment_and_no_shell_false_positive(self):
        rows = ('10 10 /venv/bin/python /venv/bin/vllm serve model\n'
                '20 20 /bin/bash -c python vllm serve model\n'
                '30 30 /venv/bin/python /venv/bin/vllm serve ownmodel\n')
        cards = {0: {'uuid': 'GPU-a'}, 1: {'uuid': 'GPU-b'}}
        with patch.object(idle, 'command', return_value=SimpleNamespace(stdout=rows)), \
                patch.object(Path, 'read_bytes', return_value=b'CUDA_VISIBLE_DEVICES=1\0'):
            self.assertEqual(idle.external_servers({30}, cards), {1})

    def test_worker_finishes_restarts_and_keeps_server(self):
        slot = object.__new__(idle.Slot)
        slot.gpu, slot.token, slot.stage = 1, 'test', 'running'
        slot.server = Mock()
        slot.server.poll.return_value = None
        slot.proxy = None
        slot.nvml_pids = {42}
        slot.last_health, slot.health_failures = 100, 0
        slot.cycles, slot.next_worker = [0] * 4, [0.0] * 4
        finished = Mock(returncode=0)
        finished.poll.return_value = 0
        active = Mock()
        active.poll.return_value = None
        slot.workers = {0: finished, 1: active, 2: active, 3: active}
        slot.processes = [slot.server, finished, active]
        slot.runner = Mock(return_value=active)
        with patch.object(idle.time, 'monotonic', return_value=101), patch.object(idle, 'event'):
            slot.step({'pids': [42]})
        slot.runner.assert_called_once_with(0)
        self.assertEqual(slot.cycles, [1, 0, 0, 0])
        self.assertIs(slot.workers[0], active)
        self.assertIn(slot.server, slot.processes)

    def test_single_dual_preemption_resume_state_machine(self):
        # 0 busy -> 1 fills; foreground reserves 1 -> yields; 0 frees -> dual fills.
        snapshots = [
            {0: {'memory_mib': 90000, 'pids': [9]}, 1: {'memory_mib': 1, 'pids': []}},
            {0: {'memory_mib': 90000, 'pids': [9]}, 1: {'memory_mib': 100000, 'pids': [8]}},
            {0: {'memory_mib': 1, 'pids': []}, 1: {'memory_mib': 1, 'pids': []}},
        ]
        created, events = [], []
        class FakeSlot:
            def __init__(self, gpu):
                self.gpu, self.stage, self.processes = gpu, 'loading', []
                created.append(gpu)
            def launch(self):
                events.append(('launch', self.gpu))
            def step(self, card):
                events.append(('step', self.gpu))
            def stop(self):
                events.append(('stop', self.gpu))
            def status(self):
                return {'stage': self.stage}
        class FakeStop:
            calls = 0
            def is_set(self):
                return self.calls >= 3
            def wait(self, _):
                self.calls += 1
        with patch.object(idle, 'STOP', FakeStop()), \
                patch.object(idle, 'lock', side_effect=lambda *a: contextlib.nullcontext()), \
                patch.object(idle, 'read', return_value={}), \
                patch.object(idle, 'save'), patch.object(idle, 'event'), \
                patch.object(Path, 'mkdir'), patch.object(idle.signal, 'signal'), \
                patch.object(idle, 'Slot', FakeSlot), \
                patch.object(idle, 'gpu_snapshot', side_effect=snapshots), \
                patch.object(idle, 'external_servers', side_effect=[{0}, {0}, set()]), \
                patch.object(idle, 'reservations', side_effect=[set(), {1}, set()]):
            idle.serve(SimpleNamespace(idle_seconds=0))
        self.assertEqual(created, [1, 0, 1])
        self.assertEqual(events[:4], [('launch', 1), ('stop', 1), ('launch', 0), ('launch', 1)])


if __name__ == '__main__':
    unittest.main()
