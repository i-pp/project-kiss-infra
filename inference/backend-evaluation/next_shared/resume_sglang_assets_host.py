"""One explicit continuation of the unused fixed SGLang GPU allowance. No actions by default."""
import argparse,json,os,sys,time,uuid
from pathlib import Path
import host_api_trial as h
from fixed_trial_assets import manifest
from low_impact_asset_verify import verify as verify_slow,RATE,BUDGET_SECONDS
from paging_telemetry import read_paging
from saved_loader_evidence import validate as reuse_static


def plan():
    rows=manifest()['required_files'];total=sum(r['bytes'] for r in rows);nominal=total/RATE
    if len(rows)!=20 or nominal>BUDGET_SECONDS or BUDGET_SECONDS+h.STARTUP_SECONDS['sglang']+90+185>h.WHOLE:
        raise h.Blocked('ASSET_SIZE_RATE_AND_WHOLE_BUDGET_INCONSISTENT')
    return {'files':20,'bytes':total,'rate_bytes_per_second':RATE,'nominal_paced_seconds':nominal,
        'asset_phase_seconds':BUDGET_SECONDS,'startup_seconds':300,'generation_seconds':90,
        'recovery_reserved_seconds':185,'whole_seconds':h.WHOLE,'baseline_reset':False}


def installed_project():
    path=Path(__file__).resolve()
    if (path.parent.name!='next_shared' or path.parent.parent.name!='backend-evaluation'
        or path.parent.parent.parent.name!='inference'):
        raise h.Blocked('FIXED_INSTALLED_RESUME_LAYOUT_REQUIRED')
    return h.safe_path(path.parents[3])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--resume-human-approved',action='store_true');args=parser.parse_args()
    if not args.resume_human_approved:
        print(json.dumps({'status':'PREPARED_FIXED_ASSET_CONTINUATION_NO_ACTIONS','model_or_container_operations':0}));return 0
    started=time.monotonic()
    if not sys.stdin.isatty() or os.getuid()==0:raise h.Blocked('NONROOT_NORMAL_HOST_TTY_REQUIRED')
    h.install_sigterm_handler()
    project=installed_project()
    operator=project/'agents/local_llm/.runtime/next-sglang-sequential-approved-20261030.json'
    record=h.operator_record(operator,h.SEQUENTIAL_OPERATOR_SHA,backend='sglang')
    if Path(record['project_root'])!=project:raise h.Blocked('RESUME_OPERATOR_PROJECT_MISMATCH')
    aiter=h.validate_aiter_retry(record,'sglang',h.SEQUENTIAL_OPERATOR_SHA)
    Coordinator,private_dir,write,probe=h.helpers();coordinator=Coordinator(record['project_root'],record);coordinator.guard()
    root=private_dir(project/'agents/local_llm/.runtime/backend-api-trials')
    marker=h.approved_attempt_path(root,'sglang',h.SEQUENTIAL_OPERATOR_SHA)
    if marker.exists() or marker.is_symlink():raise h.Blocked('APPROVED_ATTEMPT_ALREADY_RESERVED_NO_RETRY')
    run=private_dir(root/('sglang-'+uuid.uuid4().hex))
    # Preserve the old source-preflight intent. One separate explicit continuation only.
    write(root/('asset-resume-sglang-'+h.SEQUENTIAL_OPERATOR_SHA+'.json'),{'run':str(run),
        'original_gpu_operator_sha256':h.SEQUENTIAL_OPERATOR_SHA,'automatic_retry':False,
        'scope':'same-unused-GPU-allowance; paced-full20SHA; no threshold or baseline change'})
    driver=h.Docker(coordinator.guard)
    try:
        budget=plan();write(run/'asset-read-plan.json',budget);print(json.dumps({'event':'asset_read_plan',**budget}),flush=True)
        write(run/'loader-static-preflight.json',reuse_static(record,driver));write(run/'aiter-cache-profile.json',aiter)
        coordinator.guard()
    except BaseException as exc:
        write(run/'resume-preflight-failure.json',{'reason':type(exc).__name__+':'+str(exc)[:256],
            'generation_requests':0,'model_lifecycle_requests':0,'automatic_retry':False})
        print(json.dumps({'status':'BLOCKED_BEFORE_ASSET_OR_MODEL_ACTION','audit':str(run),'reason':str(exc)[:256]}),flush=True)
        return 1
    def progress(row):
        entry={'elapsed':round(time.monotonic()-started,3),**row,'diagnostic_only':True}
        try:entry['host_resources']=probe();entry['host_paging']=read_paging()
        except Exception as exc:entry['diagnostic_status']='UNAVAILABLE';entry['error_class']=type(exc).__name__
        write(run/('asset-read-'+uuid.uuid4().hex+'.json'),entry);print(json.dumps(entry),flush=True)
    def verify(directory,check):return verify_slow(directory,check=check,report=progress)
    sys.path.insert(0,str(project/'agents/local_llm'));from local_llm import policy_context
    outcome=h.Trial(record,'sglang',coordinator,driver,h.LocalHTTP(),probe,run,write,policy_context,
        verify=verify,start_time=started,reserve_attempt=lambda:h.reserve_approved_attempt(root,'sglang',h.SEQUENTIAL_OPERATOR_SHA,run),
        operator_sha256=h.SEQUENTIAL_OPERATOR_SHA).execute()
    print(json.dumps(outcome),flush=True);return 0 if outcome['status']=='COMPLETED' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_AUTOMATIC_RETRY','reason':type(exc).__name__+':'+str(exc)[:256]}),file=sys.stderr)
        raise SystemExit(1)
