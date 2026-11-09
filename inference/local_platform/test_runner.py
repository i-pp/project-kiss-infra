# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Child-only resource-limited runner for canonical pure functions and JSON cases."""
import importlib.util
import json
from pathlib import Path
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root = Path(sys.argv[1])
    spec = importlib.util.spec_from_file_location('candidate', root / 'candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = json.loads((root / 'cases.json').read_text())
    passed = 0
    failures = []
    for index, case in enumerate(cases):
        try:
            actual = getattr(module, case['function'])(*case['args'])
            equal = actual == case['expected']
            if type(equal) is not bool or not equal:
                failures.append({'case': index, 'error': 'expected value mismatch'})
            else:
                passed += 1
        except Exception as exc:
            failures.append({'case': index, 'error': type(exc).__name__})
    print(json.dumps({'total': len(cases), 'passed': passed, 'failures': failures}))
    return 0 if passed == len(cases) else 1

if __name__ == '__main__':
    raise SystemExit(main())
