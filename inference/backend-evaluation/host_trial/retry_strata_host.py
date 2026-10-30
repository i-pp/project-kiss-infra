"""One separately approved retry of the fixed NOT_RUN trial; human host only."""
import argparse
import json
import os
from pathlib import Path
import signal

import assets
import host_strata_trial as h
from notice_review import read_bound

PRIOR_RUN=h.INITIAL_FIXED_RUN
PRIOR_SHA='08399de3515876da66243cf8a95e4b8b471b7c2180aa13a498ee6b6da268790a'
SCOPE='STRATA_RETRY01_AFTER_COORDINATOR_SERVICE_RECOVERY'
APPROVAL_NAME='strata-retry01-approval-20261030.json'
INTENT_NAME='strata-retry01-intent-20261030.json'


def validate_prior(data):
    expected={'status':'FAILED','environment':'NOT_RUN','quality':'UNASSESSED',
              'generation_requests':0,'completed_generations':0,'restoration':'NOT_NEEDED',
              'code_executed':False,'source_metadata_unchanged':True}
    if any(type(data.get(k)) is not type(v) or data[k]!=v for k,v in expected.items()):
        raise h.Blocked('PRIOR_ATTEMPT_NOT_PROVEN_UNEXECUTED')
    if data.get('reason')!="FileNotFoundError:[Errno 2] No such file or directory: '/run/user/1000/agent-orchestrator/365d01e41070dcd00b66f652.sock'":
        raise h.Blocked('PRIOR_FAILURE_DIFFERS_FROM_FIXED_SOCKET_MISSING_CASE')
    return data


def validate_approval(data):
    if (data.get('approved') is not True or data.get('scope')!=SCOPE
            or data.get('prior_summary_sha256')!=PRIOR_SHA
            or type(data.get('attempt_limit')) is not int or data['attempt_limit']!=1
            or type(data.get('generation_limit')) is not int or data['generation_limit']!=1
            or type(data.get('whole_seconds')) is not int or data['whole_seconds']!=2400):
        raise h.Blocked('SEPARATE_RETRY_APPROVAL_NOT_REGISTERED')
    ref=data.get('approval_reference')
    if (not isinstance(ref,str) or not ref.startswith('Sentinel_')
            or ref=='Sentinel_710bf418f4948191a099de29ea9adcbc'
            or not isinstance(data.get('owner_approval_verified_at_utc'),str)
            or not data['owner_approval_verified_at_utc']):
        raise h.Blocked('NEW_CONFIRMED_RETRY_APPROVAL_REFERENCE_REQUIRED')
    return data


def run_once(repo, verified, coordinator, approval, trial_factory=h.Trial):
    """Check the same coordinator twice, never infer idle or change services."""
    coordinator.guard()
    marker=Path(repo)/'agents/local_llm/.runtime'/INTENT_NAME
    with coordinator.locked():
        coordinator.idle()  # read-only, same fixed endpoint; missing/busy stops before intent
        h.private_write(marker,{'scope':SCOPE,'approval_reference':approval['approval_reference'],
            'prior_run':PRIOR_RUN,'prior_summary_sha256':PRIOR_SHA,
            'automatic_retry':False,'state':'ONE_APPROVED_ATTEMPT_INTENT'})
        fd=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        fd=os.open(marker.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    # Trial reacquires the common lock and repeats idle/resource checks before unload.
    h.RUN_STARTED=True
    return trial_factory(repo,verified,coordinator).execute()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--retry-human-approved',action='store_true');a=p.parse_args()
    if not a.retry_human_approved:
        print(json.dumps({'status':'PREPARED_SEPARATE_RETRY_APPROVAL_REQUIRED',
                          'prior_run':PRIOR_RUN,'generation_requests':0}));return 0
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':
        raise h.Blocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    rt=repo/'agents/local_llm/.runtime'
    prior=json.loads(read_bound(rt/'backend-trials'/PRIOR_RUN/'summary.json',PRIOR_SHA,private=True))
    validate_prior(prior)
    approval=validate_approval(assets.private_record(rt/APPROVAL_NAME))
    verified=assets.verify(rt/'strata-reviewed-assets-20261030.json',repo)
    def interrupted(signum,frame):raise KeyboardInterrupt('HOST_RETRY_SIGNAL_'+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    result=run_once(repo,verified,h.Coordinator(repo,verified['record']),approval)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status']=='COMPLETED' and result['restoration']!='UNKNOWN' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:
        print(json.dumps({'status':'UNKNOWN_NO_RETRY' if h.RUN_STARTED else 'BLOCKED_BEFORE_TRIAL',
            'reason':type(exc).__name__+':'+str(exc)[:400],
            'generation_requests':None if h.RUN_STARTED else 0,'automatic_retry':False}))
        raise SystemExit(1)
