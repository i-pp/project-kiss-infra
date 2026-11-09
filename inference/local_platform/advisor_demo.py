# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""One-function fixture for the bounded repair client; not a general agent."""
import argparse
import json
from .repair import repair

BUGGY = 'def clamped_add(a, b, limit):\n    return min(a - b, limit)\n'
CASES = [{'function':'clamped_add','args':args,'expected':expected} for args,expected in
         [([2,3,10],5),([8,7,10],10),([-2,3,10],1),([0,0,10],0)]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--socket',required=True)
    p.add_argument('--workdir',required=True,help='new private demonstration directory only')
    args=p.parse_args()
    result=repair(args.socket,BUGGY,CASES,args.workdir)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['tests_passed'] else 1

if __name__=='__main__': raise SystemExit(main())
