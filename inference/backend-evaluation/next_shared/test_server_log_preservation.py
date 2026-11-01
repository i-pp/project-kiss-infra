"""CPU-only subprocesses/fakes; no Docker, GPU, network or model."""
import json
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock
import container_log_capture as logs
import host_api_trial as h
from test_host_api_trial import TrialTests


def child(code):
    return subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', code],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class StreamTests(unittest.TestCase):
    def test_beginning_middle_end_and_separate_stderr_retained(self):
        proc = child("import sys;sys.stdout.write('FIRST_EXCEPTION'+chr(10)+'x'*300000+chr(10)+'LAST');sys.stderr.write('STDERR')")
        data = logs.collect(proc, 3)
        self.assertTrue(data['complete_stream'], data)
        self.assertTrue(data['stdout'].startswith('FIRST_EXCEPTION'))
        self.assertTrue(data['stdout'].endswith('LAST'))
        self.assertEqual(data['stderr'], 'STDERR')
        self.assertTrue(data['cli_reaped'])

    def test_limit_retains_prefix_and_marks_incomplete(self):
        proc = child("import sys;sys.stdout.buffer.write(b'FIRST'+b'x'*(3<<20))")
        data = logs.collect(proc, 3)
        self.assertEqual(data['captured_bytes']['stdout'], logs.STREAM_LIMIT)
        self.assertTrue(data['stdout'].startswith('FIRST'))
        self.assertEqual(data['incomplete_reason'], 'LOG_STREAM_LIMIT')
        self.assertFalse(data['complete_stream'])
        self.assertTrue(data['cli_reaped'])

    def test_timeout_retains_partial_output_and_reaps_only_reader(self):
        proc = child("import sys,time;sys.stdout.write('PREFIX');sys.stdout.flush();time.sleep(2)")
        data = logs.collect(proc, .15)
        self.assertEqual(data['stdout'], 'PREFIX')
        self.assertEqual(data['incomplete_reason'], 'LOG_CAPTURE_TIMEOUT')
        self.assertTrue(data['cli_reaped'])

    def test_nonzero_cli_is_incomplete_with_stderr_preserved(self):
        data = logs.collect(child("import sys;sys.stderr.write('READ_ERROR');sys.exit(1)"), 3)
        self.assertEqual(data['stderr'], 'READ_ERROR')
        self.assertEqual(data['incomplete_reason'], 'LOG_COMMAND_FAILED')

    def test_release_errors_do_not_claim_client_reap_and_both_pipes_close(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.kill.side_effect = PermissionError('fixture')
        proc.wait.side_effect = OSError('fixture')
        proc.stdout.close.side_effect = OSError('fixture')
        with patch.object(logs.selectors, 'DefaultSelector', side_effect=OSError('fixture')):
            data = logs.collect(proc, 3)
        self.assertFalse(data['cli_reaped'])
        self.assertFalse(data['complete_stream'])
        self.assertEqual(len(data['client_release_errors']), 3)
        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_unexpected_collect_error_keeps_client_reap_unconfirmed(self):
        driver = h.Docker(lambda: None)
        with patch.object(logs.subprocess, 'Popen'), patch.object(logs, 'collect', side_effect=OSError('fixture')):
            with self.assertRaises(OSError):
                driver.logs('a' * 64)
        self.assertFalse(driver.clients_reaped)

    def test_docker_read_uses_all_logs_without_tail_or_model_command(self):
        driver = h.Docker(lambda: None)
        with patch.object(logs.subprocess, 'Popen') as spawn, patch.object(logs, 'collect', return_value={'cli_reaped': True}):
            driver.logs('a' * 64)
        self.assertEqual(spawn.call_args.args[0], ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock',
                                                 'container', 'logs', '--timestamps', 'a' * 64])
        self.assertEqual(spawn.call_args.kwargs['env'], {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})


class LogLifecycleTests(unittest.TestCase):
    setUp = TrialTests.setUp
    tearDown = TrialTests.tearDown
    execute = TrialTests.execute

    def test_full_streams_saved_without_changing_post_or_recovery(self):
        captured = {'stdout': 'FIRST' + 'x' * 300000, 'stderr': 'error',
                    'complete_stream': True, 'truncated': False}
        self.d.logs = lambda *a, **k: captured
        trial, result = self.execute()
        saved = json.loads((trial.run / 'server-log-tail.json').read_text())
        self.assertEqual(saved['stdout'], captured['stdout'])
        self.assertEqual(saved['stderr'], 'error')
        self.assertEqual(self.http.posts, 1)
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['restoration']['status'], 'RESTORED')

    def test_incomplete_log_does_not_block_recovery(self):
        self.d.logs = lambda *a, **k: {'stdout': 'PREFIX', 'stderr': '', 'complete_stream': False,
                                    'truncated': True, 'incomplete_reason': 'LOG_CAPTURE_TIMEOUT', 'cli_reaped': True}
        trial, result = self.execute()
        saved = json.loads((trial.run / 'server-log-tail.json').read_text())
        self.assertFalse(saved['complete_stream'])
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['restoration']['status'], 'RESTORED')


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (StreamTests, LogLifecycleTests))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
