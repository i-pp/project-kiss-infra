#!/usr/bin/env python3
"""Check integrated LAF Python software without models, Docker or publication.

Portable excludes only enumerated private-socket tests. Full includes those tests
and must be used only where private Unix sockets are permitted. Neither mode
establishes hardware, native-runtime, second-PC, legal or release readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

from laf_socket_test_ids import PRIVATE_SOCKET_TESTS

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    'inference.acceptance_container.test_engine',
    'inference.acceptance_container.test_run',
    'inference.acceptance_container.test_store',
    'inference.aceis_npu_service.tests.test_service',
    'inference.aceis_service.test_acceptance_profiles',
    'inference.aceis_service.test_core_integration',
    'inference.aceis_service.test_host_supervisor',
    'inference.aceis_service.test_lifecycle',
    'inference.aceis_service.test_lifecycle_uds',
    'inference.aceis_service.test_lifecycle_uds_live',
    'inference.aceis_service.test_npu_bridge',
    'inference.aceis_service.test_service',
    'inference.core_container.test_build',
    'inference.local_platform.test_cli',
    'inference.local_platform.test_cli_responses',
    'inference.local_platform.test_developer',
    'inference.local_platform.test_models',
    'inference.local_platform.test_project_runner',
    'inference.local_platform.test_repair',
    'inference.local_platform.test_workspace',
    'inference.target_acceptance.test_run',
    'test_laf_delivery',
    'test_laf_socket_runner',
)


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


def select_tests(suite, mode, socket_ids=PRIVATE_SOCKET_TESTS):
    if mode not in {'full', 'portable'}:
        raise ValueError('unknown suite')
    tests = list(flatten(suite))
    ids = [test.id() for test in tests]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('empty or duplicate test inventory')
    if any(isinstance(test, unittest.loader._FailedTest) for test in tests):
        raise ValueError('test module import failed')
    missing = set(socket_ids) - set(ids)
    if missing:
        raise ValueError('private-socket inventory is stale')
    omitted = set(socket_ids) if mode == 'portable' else set()
    selected = [test for test in tests if test.id() not in omitted]
    if not selected:
        raise ValueError('empty selected suite')
    return unittest.TestSuite(selected), len(tests), sorted(omitted)


def summary(result, planned, selected, unexecuted, mode):
    passed = (result.wasSuccessful() and result.testsRun == selected
              and not result.skipped and not result.expectedFailures
              and not result.unexpectedSuccesses
              and planned == selected + len(set(unexecuted))
              and len(unexecuted) == len(set(unexecuted)))
    return {
        'planned': planned, 'selected': selected, 'tests_run': result.testsRun,
        'failure_events': len(result.failures), 'error_events': len(result.errors),
        'skipped': len(result.skipped), 'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'selected_suite_passed': passed,
        'full_python_regression_passed': passed and mode == 'full' and not unexecuted,
        'unexecuted': [{'test': name, 'reason': 'explicit portable subset: private Unix socket required'}
                       for name in unexecuted],
    }


def source_identity():
    files = {}
    for name in ('acceptance_container', 'aceis_npu_service', 'aceis_service',
                 'core_container', 'local_platform', 'target_acceptance'):
        for path in sorted((ROOT / 'inference' / name).rglob('*.py')):
            if path.is_symlink():
                raise ValueError('source fingerprint cannot follow symlinks')
            files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ('scripts/check-laf-delivery.py', 'scripts/laf_socket_test_ids.py',
                     'scripts/test_laf_delivery.py', 'scripts/test_laf_socket_runner.py',
                     'scripts/run-laf-socket-checks.py', 'scripts/laf_socket_worker.py'):
        files[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('full', 'portable'), required=True)
    args = parser.parse_args(argv)
    sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
    # These opt-in tests are loaded in both modes, then explicitly selected.
    # Importing their modules does not create sockets or contact live services.
    os.environ['LAF_TEST_LIVE_UDS'] = '1'
    try:
        suite = unittest.TestLoader().loadTestsFromNames(MODULES)
        suite, planned, unexecuted = select_tests(suite, args.suite)
        selected = suite.countTestCases()
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
        report = summary(result, planned, selected, unexecuted, args.suite)
        report.update(schema_version=1, suite=args.suite, python_version=sys.version.split()[0],
                      source_sha256=source_identity(), p0_complete=False,
                      release_authorized=False, deployed=False,
                      scope='Unit/mocked Python software checks only; no model, Docker, native-runtime, hardware, clean-host, second-PC, legal, secret scan, publication or deployment acceptance.')
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report['selected_suite_passed'] else 1
    except (ImportError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': 'check_execution_invalid', 'error_type': type(exc).__name__,
                          'p0_complete': False, 'release_authorized': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
