"""Pure/mocked host-runner controls. Never create sockets or run the 39 tests."""
import importlib.util
import io
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
SPEC = importlib.util.spec_from_file_location('laf_host_runner', Path(__file__).with_name('run-laf-socket-checks.py'))
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)
import laf_socket_worker as worker


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as stream:
        for name, kind, data in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(data) if kind == tarfile.REGTYPE else 0
            item.linkname = '/outside' if kind == tarfile.SYMTYPE else ''
            stream.addfile(item, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return output.getvalue()


class SnapshotTests(unittest.TestCase):
    def test_checked_frozen_archive_accepts_only_bounded_named_sources(self):
        raw = archive([('scripts/laf_socket_test_ids.py', tarfile.REGTYPE, b'fixed'),
                       ('inference/aceis_service/core.py', tarfile.REGTYPE, b'code')])
        self.assertEqual(host.checked_snapshot(raw)['inference/aceis_service/core.py'], b'code')

    def test_escape_unexpected_links_duplicates_and_missing_ids_are_refused(self):
        good = ('scripts/laf_socket_test_ids.py', tarfile.REGTYPE, b'fixed')
        for bad in [('../outside', tarfile.REGTYPE, b'x'),
                    ('/outside', tarfile.REGTYPE, b'x'),
                    ('secret', tarfile.REGTYPE, b'x'),
                    ('inference/aceis_service/link', tarfile.SYMTYPE, b''), good]:
            with self.subTest(name=bad[0]), self.assertRaises(ValueError):
                host.checked_snapshot(archive([good, bad]))
        with self.assertRaises(ValueError): host.checked_snapshot(archive([]))

    def test_archive_size_bound(self):
        with self.assertRaises(ValueError): host.checked_snapshot(b'x' * (host.MAX_SOURCE_BYTES + 1))

    def test_wrong_commit_is_refused_before_source_copy(self):
        with patch.object(host, 'git', return_value=b'b'*40+b'\n') as git:
            with self.assertRaises(ValueError): host.prepare('a'*40)
        git.assert_called_once_with('rev-parse', 'HEAD')

    def test_invalid_commit_never_calls_git(self):
        with patch.object(host, 'git') as git:
            for value in ['main', 'a'*39, '-danger']:
                with self.assertRaises(ValueError): host.prepare(value)
            git.assert_not_called()


class DeadlineTests(unittest.TestCase):
    def test_child_is_separate_session_with_fixed_timeout(self):
        process = Mock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        with patch.object(host.subprocess, 'Popen', return_value=process) as start:
            value = host.run_child(['python', 'fixed'], {'PATH':'/nonexistent'}, Mock())
        self.assertTrue(start.call_args.kwargs['start_new_session'])
        process.wait.assert_called_once_with(timeout=120)
        self.assertEqual(value['process_status'], 'completed')
        self.assertTrue(value['child_stop_confirmed'])

    def test_timeout_signals_only_its_created_group(self):
        process = Mock(pid=12345)
        process.wait.side_effect = [subprocess.TimeoutExpired('fixed',120), -15]
        process.poll.side_effect = [None, -15]
        with patch.object(host.subprocess, 'Popen', return_value=process), patch.object(host.os, 'killpg') as kill:
            value = host.run_child(['python', 'fixed'], {}, Mock())
        kill.assert_called_once_with(12345, signal.SIGTERM)
        self.assertEqual(value['process_status'], 'wall_timeout')
        self.assertTrue(value['child_stop_confirmed'])

    def test_hung_term_escalates_only_same_owned_group(self):
        process = Mock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('fixed',3), -9]
        with patch.object(host.os, 'killpg') as kill:
            self.assertEqual(host.terminate_owned_group(process), -9)
        self.assertEqual([call.args for call in kill.call_args_list], [(12345,signal.SIGTERM),(12345,signal.SIGKILL)])

    def test_already_exited_child_is_not_signalled(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0
        with patch.object(host.os,'killpg') as kill:
            self.assertEqual(host.terminate_owned_group(process),0)
        kill.assert_not_called()

    def test_unconfirmed_stop_is_not_reported_as_success(self):
        process=Mock(pid=12345)
        process.poll.return_value=None
        process.wait.side_effect=subprocess.TimeoutExpired('fixed',3)
        with patch.object(host.os,'killpg'), self.assertRaises(RuntimeError):
            host.terminate_owned_group(process)


class GuardTests(unittest.TestCase):
    def test_guard_blocks_external_process_network_and_production_socket_paths(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(worker.sys,'addaudithook'):
            guard=worker.install_guard(directory)
            for event,args in [('subprocess.Popen',()),('os.system',()),('ctypes.dlopen',()),
                               ('os.fork',()),('os.forkpty',()),
                               ('socket.__new__',(None,2,1,0)),
                               ('socket.connect',(None,'/run/user/1000/aceis-inference/service.sock')),
                               ('socket.bind',(None,'\0abstract'))]:
                with self.subTest(event=event), self.assertRaises(PermissionError):guard(event,args)
            guard('socket.connect',(None,str(Path(directory)/'fake.sock')))

    def test_guard_rejects_external_writes_and_source_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(worker.sys,'addaudithook'):
            guard=worker.install_guard(directory)
            with self.assertRaises(PermissionError):guard('open',('/outside','w',worker.os.O_WRONLY))
            with self.assertRaises(PermissionError):guard('os.rename',(str(Path(directory)/'x'),'/outside'))
            guard('open',(str(Path(directory)/'new'),'w',worker.os.O_WRONLY))
            guard('open',('/stdlib/read_only.py','r',0))

    def test_worker_incomplete_skip_or_expected_failure_never_passes(self):
        result=unittest.TestResult();result.testsRun=39
        self.assertTrue(worker.result_summary(result,39)['selected_suite_passed'])
        self.assertFalse(worker.result_summary(result,40)['selected_suite_passed'])
        for field in ('skipped','expectedFailures','unexpectedSuccesses','failures','errors'):
            result=unittest.TestResult();result.testsRun=39
            getattr(result,field).append('fixture')
            self.assertFalse(worker.result_summary(result,39)['selected_suite_passed'])

    def test_missing_malformed_and_symlink_worker_evidence_are_nonpasses(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'worker.json'
            self.assertEqual(host.read_worker_result(path),(None,'missing'))
            path.write_text('{"planned":')
            self.assertEqual(host.read_worker_result(path),(None,'unreadable_or_malformed'))
            path.write_bytes(b'\xff')
            self.assertEqual(host.read_worker_result(path),(None,'unreadable_or_malformed'))
            path.unlink();path.symlink_to(Path(directory)/'other')
            self.assertEqual(host.read_worker_result(path),(None,'invalid_file'))

    def test_worker_object_is_recovered_without_hiding_missing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'worker.json';path.write_text('{"planned":39}')
            self.assertEqual(host.read_worker_result(path),({'planned':39},'available'))


if __name__=='__main__':unittest.main()
