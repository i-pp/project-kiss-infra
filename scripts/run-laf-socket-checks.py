#!/usr/bin/env python3
"""Prepare or run exactly 39 frozen fake-provider AF_UNIX tests on the host.

Use --plan here. Execute only from an authorized host terminal where private
Unix sockets are permitted. No Docker, model, service, network or auth changes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = '812ae759d98b023ebda4ce5ddef5689069d94fed'
SOURCE_PATHS = (
    'inference/acceptance_container', 'inference/aceis_npu_service',
    'inference/aceis_service', 'inference/core_container',
    'inference/local_platform', 'inference/target_acceptance',
    'scripts/laf_socket_test_ids.py',
)
RUNNER_PATHS = ('scripts/run-laf-socket-checks.py', 'scripts/laf_socket_worker.py')
WALL_SECONDS = 120
MAX_SOURCE_BYTES = 2 * 1024**2


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=10).stdout


def checked_snapshot(raw):
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('source archive exceeds bound')
    files = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for item in archive:
            path = PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts or str(path) != item.name:
                raise ValueError('unsafe archive path')
            if item.isdir():
                continue
            if not item.isfile() or not any(item.name == prefix or item.name.startswith(prefix + '/') for prefix in SOURCE_PATHS):
                raise ValueError('unexpected source archive entry')
            if item.name in files:
                raise ValueError('duplicate source archive entry')
            total += item.size
            if total > MAX_SOURCE_BYTES:
                raise ValueError('source bytes exceed bound')
            files[item.name] = archive.extractfile(item).read()
    if not files or 'scripts/laf_socket_test_ids.py' not in files:
        raise ValueError('source inventory incomplete')
    return files


def prepare(runner_commit):
    if not re.fullmatch('[0-9a-f]{40}', runner_commit):
        raise ValueError('exact local runner commit required')
    if git('rev-parse', 'HEAD').decode().strip() != runner_commit:
        raise ValueError('checkout HEAD differs from expected runner commit')
    git('merge-base', '--is-ancestor', SOURCE_COMMIT, runner_commit)
    for relative in RUNNER_PATHS:
        path = ROOT / relative
        if path.is_symlink() or path.read_bytes() != git('show', runner_commit + ':' + relative):
            raise ValueError('runner source differs from committed bytes')
    files = checked_snapshot(git('archive', '--format=tar', SOURCE_COMMIT, '--', *SOURCE_PATHS))
    files['scripts/laf_socket_worker.py'] = (ROOT / 'scripts/laf_socket_worker.py').read_bytes()
    return files


def terminate_owned_group(process):
    if process.poll() is not None:
        return process.returncode
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
    raise RuntimeError('owned test process stop not confirmed')


def run_child(command, env, log):
    start = time.monotonic()
    try:
        process = subprocess.Popen(command, cwd=str(ROOT), env=env,
                                   stdout=log, stderr=log, start_new_session=True)
    except OSError as exc:
        return {'process_status': 'launch_failed', 'returncode': None,
                'wall_seconds': time.monotonic() - start,
                'child_stop_confirmed': True, 'error_type': type(exc).__name__}
    status = 'completed'
    try:
        code = process.wait(timeout=WALL_SECONDS)
    except subprocess.TimeoutExpired:
        status = 'wall_timeout'
        try:
            code = terminate_owned_group(process)
        except RuntimeError:
            status, code = 'stop_unconfirmed', process.poll()
    except KeyboardInterrupt:
        status = 'interrupted'
        try:
            code = terminate_owned_group(process)
        except RuntimeError:
            status, code = 'stop_unconfirmed', process.poll()
    return {'process_status': status, 'returncode': code,
            'wall_seconds': time.monotonic() - start,
            'owned_child_pid': process.pid,
            'child_stop_confirmed': process.poll() is not None}


def read_worker_result(path):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 256 * 1024:
            return None, 'invalid_file'
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            return None, 'invalid_shape'
        return value, 'available'
    except FileNotFoundError:
        return None, 'missing'
    except (OSError, ValueError, UnicodeError):
        return None, 'unreadable_or_malformed'


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner-commit', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--evidence', help='new private evidence directory; never overwrite')
    args = parser.parse_args(argv)
    files = prepare(args.runner_commit)
    manifest = {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}
    plan = {'source_commit': SOURCE_COMMIT, 'runner_commit': args.runner_commit,
            'planned_tests': 39, 'wall_limit_seconds': WALL_SECONDS,
            'term_and_kill_wait_seconds': 6, 'source_sha256': manifest,
            'scope': 'frozen fake-provider socket tests only',
            'full_python_regression_passed': False, 'p0_complete': False,
            'release_authorized': False}
    if args.plan:
        print(json.dumps(dict(plan, tests_executed=False), indent=2, sort_keys=True))
        return 0
    evidence = Path(args.evidence).absolute()
    evidence.mkdir(mode=0o700)  # Existing targets and symlinks are refused.
    os.umask(0o077)
    source = evidence / 'source'
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o400)
    write_json(evidence / 'plan.json', plan)
    scratch = Path(tempfile.mkdtemp(prefix='laf-sock-', dir='/tmp'))
    execution = {'child_stop_confirmed': True}
    try:
        scratch.chmod(0o700)
        env = {'PATH': '/nonexistent', 'HOME': str(scratch), 'TMPDIR': str(scratch),
               'LANG': 'C.UTF-8', 'LAF_TEST_LIVE_UDS': '1'}
        command = [sys.executable, '-I', '-B', str(source / 'scripts/laf_socket_worker.py'),
                   '--scratch', str(scratch)]
        with (evidence / 'tests.log').open('xb') as log:
            execution = run_child(command, env, log)
        worker, worker_evidence_status = read_worker_result(scratch / 'worker-result.json')
        current = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}
        source_unchanged_at_endpoints = manifest == current
        passed = (execution['process_status'] == 'completed' and execution['returncode'] == 0
                  and execution['child_stop_confirmed'] and source_unchanged_at_endpoints
                  and isinstance(worker, dict) and worker.get('selected_suite_passed') is True
                  and worker.get('tests_run') == worker.get('planned') == 39
                  and all(worker.get(key) == 0 for key in ('failure_events', 'error_events', 'skipped', 'expected_failures', 'unexpected_successes')))
        report = dict(plan, execution=execution, worker=worker,
                      worker_evidence_status=worker_evidence_status,
                      retained_scratch=None if execution['child_stop_confirmed'] else str(scratch),
                      snapshot_unchanged_at_endpoints=source_unchanged_at_endpoints,
                      selected_suite_passed=passed,
                      limits='Audit guard is not a general sandbox; endpoint hashes do not prove continuous immutability. No current-tree container, hardware, second-PC or public readiness claim.')
        write_json(evidence / 'result.json', report)
    finally:
        if execution['child_stop_confirmed']:
            shutil.rmtree(scratch)
    print(json.dumps({'selected_suite_passed': passed, 'evidence': str(evidence),
                      'process_status': execution['process_status']}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
