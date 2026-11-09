"""Child for the frozen, fake-provider socket suite. Never launch directly.

The audit guard is defense against accidental live access by these reviewed
stdlib tests, not a general security sandbox for untrusted Python code.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import socket
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def result_summary(result, planned):
    passed = (result.wasSuccessful() and result.testsRun == planned
              and not result.skipped and not result.expectedFailures
              and not result.unexpectedSuccesses)
    return {'planned': planned, 'tests_run': result.testsRun,
            'failure_events': len(result.failures), 'error_events': len(result.errors),
            'skipped': len(result.skipped), 'expected_failures': len(result.expectedFailures),
            'unexpected_successes': len(result.unexpectedSuccesses),
            'selected_suite_passed': passed, 'full_python_regression_passed': False,
            'p0_complete': False, 'release_authorized': False}


def install_guard(scratch):
    scratch = Path(scratch).resolve()

    def private_path(value):
        if not isinstance(value, (str, bytes, os.PathLike)):
            raise PermissionError('private test path required')
        if isinstance(value, bytes):
            value = os.fsdecode(value)
        if not value or '\0' in str(value):
            raise PermissionError('abstract or empty socket path forbidden')
        path = Path(value).resolve()
        if not path.is_relative_to(scratch):
            raise PermissionError('test mutation or connection outside private scratch forbidden')

    def guard(event, args):
        if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn',
                     'os.fork', 'os.forkpty', 'ctypes.dlopen'}:
            raise PermissionError('external execution forbidden by socket-test guard')
        if event == 'socket.__new__' and args[1] != socket.AF_UNIX:
            raise PermissionError('only AF_UNIX test sockets permitted')
        if event in {'socket.bind', 'socket.connect', 'socket.sendto'}:
            private_path(args[1])
        if event == 'open' and not isinstance(args[0], int):
            flags = args[2]
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                private_path(args[0])
        if event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.chown', 'os.truncate'}:
            private_path(args[0])
        if event in {'os.rename', 'os.link', 'os.symlink'}:
            private_path(args[0]); private_path(args[1])
    sys.addaudithook(guard)
    return guard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', required=True)
    args = parser.parse_args(argv)
    scratch = Path(args.scratch).resolve()
    if not scratch.is_dir() or scratch.stat().st_uid != os.getuid() or scratch.stat().st_mode & 0o077:
        raise ValueError('owned private scratch directory required')
    os.chdir(scratch)
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    os.environ['LAF_TEST_LIVE_UDS'] = '1'
    os.environ['TMPDIR'] = str(scratch)
    import tempfile
    tempfile.tempdir = str(scratch)
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / 'scripts')]
    install_guard(scratch)
    from laf_socket_test_ids import PRIVATE_SOCKET_TESTS
    ids = sorted(PRIVATE_SOCKET_TESTS)
    suite = unittest.TestLoader().loadTestsFromNames(ids)
    tests = list(flatten(suite))
    if len(ids) != 39 or sorted(t.id() for t in tests) != ids:
        raise ValueError('exact frozen 39-test inventory required')
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(unittest.TestSuite(tests))
    report = result_summary(result, len(ids))
    report['test_ids'] = ids
    (scratch / 'worker-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['selected_suite_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
