#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

import datetime
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'evaluation/coder/repair'))
from sandbox import execute

destination = root/(sys.argv[1] if len(sys.argv)==2 else 'logs/repair-isolation.json')
if not destination.resolve().is_relative_to(root/'logs'): raise SystemExit('Output must be under logs/')
if destination.exists(): raise SystemExit('Preserve existing isolation report before another run')
records = {}
records['permissions'] = execute(['python3','/suite/repair/isolation_probe.py'])
assert records['permissions']['state']['ExitCode'] == 0, records['permissions']['output']
assert json.loads(records['permissions']['output'])['checks'] == 'PASS'
records['timeout'] = execute(['python3','-c','import time; time.sleep(30)'],seconds=2)
assert records['timeout']['limit_reason'] == 'wall_timeout'
records['output_limit'] = execute(['python3','-c','import os; os.write(1,b"x"*(2*1024*1024))'],output_limit=65536)
assert records['output_limit']['limit_reason'] == 'output_limit'
records['memory_limit'] = execute(['python3','-c','x=bytearray(128*1024*1024)'],memory=64*1024**2)
assert records['memory_limit']['state']['OOMKilled'], records['memory_limit']
report = {'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'checks':'PASS','records':records}
with destination.open('x') as output: json.dump(report,output,indent=2)
print('Isolation, non-root, no network/GPU, resource limits, timeout, output cap and bounded OOM probe: PASS')
