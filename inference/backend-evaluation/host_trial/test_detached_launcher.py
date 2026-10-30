from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_strata_retry02 as l


class Coordinator:
    def guard(self): pass
    @contextmanager
    def locked(self): yield
    def idle(self): pass


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rt = self.root / 'runtime'
        self.rt.mkdir(mode=0o700)
        self.helpers = self.root / 'inference/backend-evaluation/host_trial'
        self.helpers.mkdir(parents=True)
        self.approval = self.rt / 'strata-retry02-approval-20261030.json'
        l.write_once(self.approval, {'approved': True,
            'scope': 'STRATA_RETRY02_AFTER_ACCIDENTAL_INTERRUPT',
            'approval_reference': 'Sentinel_NEW_APPROVAL_FIXTURE'})
        self.mods = patch.dict(sys.modules, {
            'assets': SimpleNamespace(private_record=lambda p: {}),
            'host_strata_trial': SimpleNamespace(Coordinator=lambda *a: Coordinator())})
        self.mods.start(); self.addCleanup(self.mods.stop)

    def start(self, run):
        return l.start(self.root, self.helpers, self.rt, run)

    def test_unapproved_record_never_spawns(self):
        self.approval.unlink()
        l.write_once(self.approval, {'approved': False})
        with self.assertRaisesRegex(RuntimeError, 'APPROVAL'):
            self.start(lambda *a, **k: self.fail('spawned'))
        self.assertFalse(l.paths(self.rt)['launch'].exists())

    def test_start_fixed_argv_and_duplicate_refused(self):
        calls = []
        def run(argv, **kw):
            calls.append((argv, kw)); return SimpleNamespace(returncode=0)
        result = self.start(run)
        self.assertEqual(result['status'], 'DETACHED_LAUNCHED_NOT_TRIAL_SUCCESS')
        self.assertEqual(calls[0][0][:8], ['/usr/bin/tmux', '-L', l.SESSION,
            '-f', '/dev/null', 'new-session', '-d', '-s'])
        self.assertNotIn('shell', calls[0][1])
        self.assertTrue(calls[0][0][-1] == '--worker')
        with self.assertRaisesRegex(RuntimeError, 'PRIOR_LAUNCH'):
            self.start(run)
        self.assertEqual(len(calls), 1)

    def test_unknown_spawn_keeps_single_use_intent(self):
        def run(*a, **k): raise TimeoutError()
        with self.assertRaisesRegex(RuntimeError, 'UNCERTAIN'):
            self.start(run)
        self.assertTrue(l.paths(self.rt)['launch'].exists())
        with self.assertRaisesRegex(RuntimeError, 'PRIOR_LAUNCH'):
            self.start(run)

    def test_busy_does_not_consume_intent_or_spawn(self):
        with patch.object(Coordinator, 'idle', side_effect=RuntimeError('busy')):
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                self.start(lambda *a, **k: self.fail('spawned'))
        self.assertFalse(l.paths(self.rt)['launch'].exists())

    def test_host_guard_cannot_be_bypassed_by_start(self):
        with patch.object(Coordinator, 'guard', side_effect=RuntimeError('host only')):
            with self.assertRaisesRegex(RuntimeError, 'host only'):
                self.start(lambda *a, **k: self.fail('spawned'))
        self.assertFalse(l.paths(self.rt)['launch'].exists())

    def test_worker_logs_exit_and_does_not_kill_on_outer_deadline(self):
        digest = l.approval_digest(self.approval)
        l.write_once(l.paths(self.rt)['launch'], {'approval_sha256': digest})
        def run(argv, **kw):
            self.assertEqual(argv[-2:], [str(self.helpers/'retry02_strata_host.py'), '--retry-human-approved'])
            self.assertNotIn('timeout', kw)
            kw['stdout'].write('fixed fake trial terminal output\n')
            return SimpleNamespace(wait=lambda:1)
        result = l.worker(self.root, self.helpers, self.rt, run)
        self.assertEqual(result['controller_exit_code'], 1)
        self.assertEqual((self.rt/'strata-retry02-terminal.log').read_text(), 'fixed fake trial terminal output\n')
        self.assertEqual((self.rt/'strata-retry02-terminal.log').stat().st_mode & 0o777, 0o600)
        self.assertTrue(l.paths(self.rt)['result'].exists())

    def test_keyboard_interrupt_waits_on_same_handle_without_respawn(self):
        digest = l.approval_digest(self.approval)
        l.write_once(l.paths(self.rt)['launch'], {'approval_sha256': digest})
        calls = []
        class Child:
            count = 0
            def wait(self):
                self.count += 1
                if self.count == 1: raise KeyboardInterrupt()
                return 1
        child = Child()
        def spawn(*argv, **kw):
            calls.append(argv)
            kw['stdout'].write(json.dumps({'run_directory':'fake/run', 'status':'FAILED',
                'generation_requests':0, 'restoration':'RESTORED'})+'\n')
            return child
        result = l.worker(self.root, self.helpers, self.rt, spawn)
        self.assertEqual(len(calls), 1)
        self.assertEqual(child.count, 2)
        self.assertEqual(result['wrapper_signals_observed'], [2])
        self.assertEqual(result['controller_reported_trial']['restoration'], 'RESTORED')

    def test_worker_approval_change_prevents_trial(self):
        l.write_once(l.paths(self.rt)['launch'], {'approval_sha256': '0'*64})
        with self.assertRaisesRegex(RuntimeError, 'APPROVAL_CHANGED'):
            l.worker(self.root, self.helpers, self.rt, lambda *a, **k:self.fail('trial'))
        self.assertFalse(l.paths(self.rt)['worker'].exists())

    def test_symlink_private_record_refused(self):
        target = self.root/'link.json'; target.symlink_to(self.approval)
        with self.assertRaisesRegex(RuntimeError, 'SYMLINK'):
            l.private_json(target)


if __name__ == '__main__': unittest.main()
