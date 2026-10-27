#!/usr/bin/env python3
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'evaluation/coder/repair'))
from sandbox import execute

destination = root/'logs/repair-runner-controls.json'
if destination.exists(): raise SystemExit('Preserve previous control results first')
tasks = [t for t in json.loads((root/'evaluation/coder/tasks.json').read_text()) if t['kind']=='code']
results = {}
for variant, expected in [('positive','PASS'),('negative','FAIL')]:
    for task in tasks:
        run = execute(['python3','/suite/repair/runner.py',task['id']],
                      candidate=root/f'logs/coder/control-{variant}')
        assert run['state']['ExitCode']==0 and not run['limit_reason'], run['output']
        result = json.loads(run['output'])
        assert result['status']==expected, (variant,task['id'],result)
        results[variant+'/'+task['id']] = {'sandbox':run,'verifier':result}
        print(variant,task['id'],result['status'],flush=True)
with destination.open('x') as output: json.dump({'checks':'PASS','results':results},output,indent=2)
