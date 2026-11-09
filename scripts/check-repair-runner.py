#!/usr/bin/env python3
# KISS Open License Version 1.0 (KOL-v1)
#
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1
#
# Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
# Contributors may add copyright notices for their own original modifications.
# Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
#
# Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
# without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
#
# Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
# KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
#
# This header is a summary, not a separate license or an amendment to KOL-v1.
# All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

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
