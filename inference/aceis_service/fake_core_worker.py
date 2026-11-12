"""Test fixture only. Excluded from the Core image allowlist."""
import json
import os
import subprocess
import sys

child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3600)'])
print(json.dumps({'starting': True, 'engine_pid': child.pid}), flush=True)
print(json.dumps({'ready': True, 'engine_pid': child.pid}), flush=True)
if os.environ.get('LAF_TEST_WRAPPER_EXIT') == '1':
    raise SystemExit(0)
for line in sys.stdin:
    body = json.loads(line)
    print(json.dumps({'content': 'fake Flash', 'finish_reason': 'stop',
                      'prompt_tokens': 1, 'completion_tokens': 1}), flush=True)
