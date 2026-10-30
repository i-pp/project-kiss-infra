"""Read-only recovery evidence. Never signals, loads, clears UNKNOWN or retries."""
import argparse
import json
from pathlib import Path
import re
import sys


def inspect_saved(root,run_id):
    if re.fullmatch(r'strata-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}',run_id) is None:raise ValueError('Fixed Strata run ID required')
    root=Path(root)
    if any(p.is_symlink() for p in [root,*root.parents]):raise ValueError('No symlink runtime ancestry')
    directory=root/'backend-trials'/run_id
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Existing owned run directory required')
    result={'run_id':run_id,'read_only':True,'automatic_retry':False,'automatic_restore':False,
            'shared_unknown_present':(root/'UNCERTAIN.json').exists(),
            'strata_unknown_present':(root/'backend-trials/strata-UNCERTAIN.json').exists(),
            'action':'Inspect ownership, resources and authoritative state with operator; do not remove markers or rerun'}
    summary=directory/'summary.json'
    if summary.exists():
        if summary.is_symlink() or summary.stat().st_size>1048576:raise ValueError('Unsafe saved summary')
        data=json.loads(summary.read_text());result['summary']={k:data.get(k) for k in ['status','reason','restoration','restore_error','generation_requests','generation_uncertain','source_metadata_unchanged','resources_after']}
    else:result['summary']='MISSING_CONTROLLER_MAY_HAVE_DIED'
    native=directory/'native.json'
    if native.exists():
        if native.is_symlink() or native.stat().st_size>8<<20:raise ValueError('Unsafe native evidence')
        data=json.loads(native.read_text());result['saved_owned_cleanup']=data.get('cleanup')
        result['saved_root_identity']=data.get('root_identity')
    else:result['saved_owned_cleanup']='NOT_PROVEN_FROM_NATIVE_EVIDENCE'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id',required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'agents/local_llm'))
    from local_llm import RUNTIME
    from model_runtime import Runtime
    result=inspect_saved(RUNTIME,a.run_id)
    result['router_status']=Runtime().status('qwen-coder-30b')
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
