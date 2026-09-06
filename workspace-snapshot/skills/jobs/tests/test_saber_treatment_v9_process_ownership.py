"""Pure mocks: never enumerate, signal, sleep for, or spawn a real process."""

import copy
import importlib.util
import json
from pathlib import Path
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / 'saber_treatment_v9_process_ownership.py'
SPEC = importlib.util.spec_from_file_location('ownership', PATH)
ownership = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ownership)
READ_STAT = ownership._read_stat
BATCH = 'v9-full-20260905-r1'
MODEL = 'mistral'
BOOT = '12345678-1234-1234-1234-123456789abc'


def row(pid, birth=None, pgid=100, sid=100, state='S'):
    return {'pid': pid, 'birth': birth or pid * 10, 'pgid': pgid, 'sid': sid, 'state': state}


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.processes = {100: row(100), 101: row(101), 102: row(102)}
        self.environ = {100: [f'SABER_BATCH_ID={BATCH}'.encode(),
                              f'SABER_BATCH_MODEL={MODEL}'.encode()]}
        self.clock = 0.0
        self.fds = {}
        self.signals = []
        self.closed = []
        self.on_signal = lambda pid, sig: self.processes.pop(pid, None)
        mocks = (
            patch.object(ownership, '_boot_id', return_value=BOOT),
            patch.object(ownership, '_scan', side_effect=lambda: copy.deepcopy(self.processes)),
            patch.object(ownership, '_read_stat', side_effect=lambda pid: copy.deepcopy(self.processes.get(pid))),
            patch.object(ownership, '_read_environ', side_effect=lambda pid: self.environ.get(pid, [])),
            patch.object(ownership.os, 'getpgrp', return_value=999),
            patch.object(ownership.os, 'getsid', return_value=999),
            patch.object(ownership.os, 'pidfd_open', side_effect=self.open_fd),
            patch.object(ownership.signal, 'pidfd_send_signal', side_effect=self.send_fd),
            patch.object(ownership.os, 'close', side_effect=self.closed.append),
            patch.object(ownership.os, 'kill', side_effect=AssertionError('no bare PID signals')),
            patch.object(ownership.os, 'killpg', side_effect=AssertionError('no group-number signals')),
            patch.object(ownership.time, 'monotonic', side_effect=lambda: self.clock),
            patch.object(ownership.time, 'sleep', side_effect=self.sleep),
        )
        for mocked in mocks:
            mocked.start()
            self.addCleanup(mocked.stop)

    def sleep(self, seconds):
        self.clock += seconds

    def open_fd(self, pid, flags):
        self.assertEqual(flags, 0)
        if pid not in self.processes:
            raise ProcessLookupError
        fd = 1000 + len(self.fds)
        self.fds[fd] = (pid, self.processes[pid]['birth'])
        return fd

    def send_fd(self, fd, sig, info, flags):
        pid, birth = self.fds[fd]
        current = self.processes.get(pid)
        if current is None or current['birth'] != birth:
            raise ProcessLookupError
        self.signals.append((pid, sig))
        self.on_signal(pid, sig)

    def capture(self):
        return ownership.capture(100, BATCH, MODEL)

    def test_capture_records_untagged_children_and_no_environment(self):
        record = self.capture()
        self.assertEqual([p['pid'] for p in record['members']], [100, 101, 102])
        self.assertEqual(record['boot_id'], BOOT)
        self.assertNotIn('SABER_BATCH_ID', json.dumps(record))
        report = ownership.inspect([record], BATCH, MODEL)
        self.assertTrue(report['passed'])
        self.assertEqual(report['groups'][0]['active_pids'], [100, 101, 102])
        self.assertEqual(self.signals, [])

    def test_leader_requires_both_tags_and_independent_session(self):
        self.environ[100] = []
        with self.assertRaises(ownership.OwnershipError):
            self.capture()
        self.environ[100] = [f'SABER_BATCH_ID={BATCH}'.encode(),
                             f'SABER_BATCH_MODEL={MODEL}'.encode()]
        self.processes[100]['sid'] = 99
        with self.assertRaises(ownership.OwnershipError):
            self.capture()

    def test_child_explicit_conflicting_tag_rejected_before_any_signal(self):
        record = self.capture()
        self.environ[102] = [b'SABER_BATCH_MODEL=foreign']
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_pid_reuse_boot_and_scope_mismatch_rejected(self):
        original = self.capture()
        for field, value in [('boot_id', 'other-boot'), ('batch', 'foreign'), ('birth', 1)]:
            changed = copy.deepcopy(original)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([changed], BATCH, MODEL, 0, 0)
        self.processes[101]['birth'] += 1
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([original], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_leader_exited_known_child_anchors_cleanup(self):
        record = self.capture()
        self.processes.pop(100)
        ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertEqual(self.signals, [(101, signal.SIGTERM), (102, signal.SIGTERM)])

    def test_leader_exits_after_term_children_anchor_kill(self):
        record = self.capture()
        def stop(pid, sig):
            if pid == 100 or sig == signal.SIGKILL:
                self.processes.pop(pid, None)
        self.on_signal = stop
        ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertEqual(self.signals, [(100, signal.SIGTERM), (101, signal.SIGTERM),
                                       (102, signal.SIGTERM), (101, signal.SIGKILL),
                                       (102, signal.SIGKILL)])
        self.assertEqual(len(self.closed), 5)

    def test_unobserved_member_without_surviving_anchor_refused(self):
        record = self.capture()
        self.processes = {110: row(110)}
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_new_members_are_recorded_only_with_current_anchor(self):
        record = self.capture()
        self.processes[110] = row(110)
        updated = ownership.validate([record], BATCH, MODEL)['records'][0]
        self.assertEqual(len(record['members']), 3)
        self.assertEqual(len(updated['members']), 4)
        self.processes = {110: self.processes[110]}
        ownership.cleanup([updated], BATCH, MODEL, 0, 0)
        self.assertEqual(self.signals, [(110, signal.SIGTERM)])

    def test_zero_group_members_is_safe_noop_but_old_pid_only_record_rejected(self):
        record = self.capture()
        self.processes = {}
        ownership.cleanup([record], BATCH, MODEL)
        self.assertFalse(self.signals)
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([{'pid': 100}], BATCH, MODEL)

    def test_changed_member_session_or_escaped_group_refused(self):
        record = self.capture()
        self.processes[110] = row(110, pgid=110)
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_pid_changes_during_pidfd_open_refused_before_signals(self):
        record = self.capture()
        original = self.open_fd
        def changing(pid, flags):
            fd = original(pid, flags)
            if pid == 102:
                self.processes[pid]['birth'] += 1
            return fd
        with patch.object(ownership.os, 'pidfd_open', side_effect=changing):
            with self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)
        self.assertEqual(len(self.closed), 3)

    def test_stuck_group_is_failure_not_success(self):
        record = self.capture()
        self.on_signal = lambda pid, sig: None
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([record], BATCH, MODEL, 0.4, 0.4)
        self.assertEqual(len(self.signals), 6)
        self.assertGreaterEqual(self.clock, 0.8)

    def test_conflict_in_second_group_prevents_signalling_first_group(self):
        first = self.capture()
        self.processes[200] = row(200, pgid=200, sid=200)
        self.environ[200] = list(self.environ[100])
        second = ownership.capture(200, BATCH, MODEL)
        self.environ[200] = [b'SABER_BATCH_ID=foreign']
        with self.assertRaises(ownership.OwnershipError):
            ownership.cleanup([first, second], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_zombie_only_group_is_noop(self):
        record = self.capture()
        for item in self.processes.values():
            item['state'] = 'Z'
        ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)

    def test_duplicate_records_and_caller_group_are_rejected(self):
        record = self.capture()
        with self.assertRaises(ownership.OwnershipError):
            ownership.inspect([record, record], BATCH, MODEL)
        with patch.object(ownership.os, 'getpgrp', return_value=100):
            with self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([record], BATCH, MODEL)

    def test_invalid_timeouts_and_missing_pidfd_are_rejected(self):
        record = self.capture()
        for value in (-1, float('inf'), True, '45'):
            with self.subTest(value=value), self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([record], BATCH, MODEL, term_timeout=value)
        with patch.object(ownership, 'signal', SimpleNamespace(SIGTERM=signal.SIGTERM, SIGKILL=signal.SIGKILL)):
            with self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)


    def test_proc_stat_birth_field_and_parenthesized_title(self):
        fields = ['S', '1', '123', '123'] + ['0'] * 15 + ['456789']
        content = '123 (vLLM (EngineCore)) ' + ' '.join(fields)
        with patch.object(Path, 'read_text', return_value=content):
            parsed = READ_STAT(123)
        self.assertEqual(parsed, {'pid': 123, 'birth': 456789,
                                  'pgid': 123, 'sid': 123, 'state': 'S'})
        with patch.object(Path, 'read_text', return_value='123 (bad) truncated'):
            with self.assertRaises(ownership.OwnershipError):
                READ_STAT(123)

    def test_new_conflict_after_pinning_prevents_all_signals(self):
        record = self.capture()
        original = self.open_fd
        def conflicting(pid, flags):
            fd = original(pid, flags)
            if pid == 102:
                self.processes[110] = row(110)
                self.environ[110] = [b'SABER_BATCH_MODEL=foreign']
            return fd
        with patch.object(ownership.os, 'pidfd_open', side_effect=conflicting):
            with self.assertRaises(ownership.OwnershipError):
                ownership.cleanup([record], BATCH, MODEL, 0, 0)
        self.assertFalse(self.signals)
        self.assertEqual(len(self.closed), 3)


if __name__ == '__main__':
    unittest.main()
