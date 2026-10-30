"""Resolve one terminal zero-generation-POST trial record, never allocate or infer.

Owner-approved fixed-case resolver. Resource telemetry is recorded, not used to decide
whether a finished, absent, zero-generation-POST trial's historical outcome is known.
Normal allocation/inference resource guards remain in their existing modules.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import traceback
import uuid

APPROVAL_REQUEST='Sentinel_6c0fb32e13908191bf086409fc0a8cec'
SOURCES={'reconcile_vllm_readiness':'1488e529c34e0d1d554b1106dbb7edf226883991e45719ce26fc6ec1b2a0b4f5',
    'recover_router_postboot':'708e5b770ec40b7a4433109099022b7eb672a6c710b31e4724521b62354a1571',
    'reconcile_restored_swap':'afcf74b93fcf0a69f80a7da09d468a25b3c552340b6042931249692f062334dd'}


class Blocked(RuntimeError):pass


def validate_restoration(value,r):
    props=value.get('properties') or {};slots=value.get('slots')
    if (value.get('models')!=r.STATES or value.get('health',{}).get('status')!='ok'
            or props.get('model_alias')!=r.MODEL or type(props.get('total_slots')) is not int or props['total_slots']!=1
            or type(props.get('default_generation_settings',{}).get('n_ctx')) is not int
            or props['default_generation_settings']['n_ctx']!=32768 or not isinstance(slots,list)
            or len(slots)!=1 or slots[0].get('is_processing') is not False):
        raise Blocked('CURRENT_30B_RESTORATION_NOT_CONFIRMED')
    return value


def observe_restoration(c,r):
    """GET/status only, deliberately does not call allocation preflight/idle()."""
    c.guard();c.c.rt.require_deployment();c.daemon_observe();end=time.monotonic()+15
    value={'models':c.c.rt.snapshot(end),'health':c.c.rt.read('/health',end),
        'properties':c.c.rt.read('/props?model='+r.MODEL+'&autoload=false',end),
        'slots':c.c.rt.read('/slots?model='+r.MODEL+'&autoload=false',end)}
    try:value['resources']={'status':'OBSERVED_NOT_ADMISSION_GATE','values':c.c.rt.probe()}
    except Exception as exc:value['resources']={'status':'UNAVAILABLE_NOT_ADMISSION_GATE','error_class':type(exc).__name__}
    return value


def resolve(repo,r,s,h,b,case,c,docker,m,*,read_boot=None,observe=observe_restoration,rename=os.rename):
    if APPROVAL_REQUEST=='PENDING_NOT_AUTHORIZED':raise Blocked('TERMINAL_RESOLUTION_APPROVAL_PENDING')
    c.guard();root=r.runtime_for(repo)
    read_boot=read_boot or s.boot
    with r.reconciliation_lock(root) as lock_fd:
        evidence=r.validate_fixed_evidence(repo,b)
        if s.load_case(repo,r,b,h)!=case:raise Blocked('FIXED_CASE_BINDING_CHANGED')
        if read_boot()!=case['boot_id']:raise Blocked('APPROVED_BOOT_CHANGED')
        parent=root/'readiness-reconciliation-audits'
        if parent.exists():
            r.safe(parent);info=parent.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
                raise Blocked('AUDIT_ROOT_UNSAFE')
        else:parent.mkdir(mode=0o700)
        audit=parent/(b['run_name']+'-terminal-'+uuid.uuid4().hex);audit.mkdir(mode=0o700)
        r.write_audit(audit/'started.json',{'approval':APPROVAL_REQUEST,'scope':'ONE_ZERO_GENERATION_POST_TERMINAL_TRIAL',
            'resources_are_admission_gate':False,'generation_requests':0,'container_mutations':0})
        r.fsync_dir(audit);r.fsync_dir(parent)
        stage='initial_identity_absence_and_restoration';current=None
        try:
            s.verify_live(m,case);c.daemon_observe()
            absent=docker.absent(b['container_id'],b['container_name'])
            # Preserve the raw observation before validation, including on failure.
            current=observe(c,r);validate_restoration(current,r)
            stage='final_identity_absence_and_restoration'
            s.verify_live(m,case);c.daemon_observe()
            current=observe(c,r);validate_restoration(current,r)
            absent_after=docker.absent(b['container_id'],b['container_name'])
            final=r.validate_fixed_evidence(repo,b)
            if (s.load_case(repo,r,b,h)!=case or final['marker_identity']!=evidence['marker_identity']
                    or read_boot()!=case['boot_id']):raise Blocked('FIXED_EVIDENCE_OR_BOOT_CHANGED')
            archived=audit/'UNCERTAIN.original.json'
            result={'status':'RESOLVED_ZERO_POST_READINESS_FAILURE_NO_GENERATION','audit_directory':str(audit),
                'archived_marker':str(archived),'resolution':str(audit/'resolution.json'),
                'original_summary':'UNKNOWN_PRESERVED','vllm_consumed_attempt_preserved':True,
                'generation_requests':0,'model_lifecycle_requests':0,'container_mutations':0,'automatic_retry':False}
            stage='durable_terminal_resolution_before_archive'
            resolution={'resolution_status':'KNOWN_ENVIRONMENT_READINESS_FAILURE_NO_GENERATION_REQUEST_SENT',
                'historical_original_status':'UNKNOWN','historical_reason':r.REASON,'environment':'FAIL',
                'quality':'UNASSESSED','generation_requests':0,'generation_request_intents':0,
                'cleanup':'FIXED_CONTAINER_ID_AND_NAME_CONFIRMED_ABSENT',
                'restoration':'CURRENT_30B_ONLY_HEALTHY_IDLE_32K_CONFIRMED',
                'consumed_attempt_preserved':True,'new_inference_authorized':False,'approval':APPROVAL_REQUEST,
                'original_marker_base64':base64.b64encode(evidence['marker_raw']).decode(),
                'original_marker_parsed':evidence['marker'],'original_summary_sha256':evidence['summary_sha256'],
                'consumed_attempt_sha256':evidence['attempt_sha256'],'case':case,
                'docker_absence_before':absent,'docker_absence_after':absent_after,'current_restoration':current,
                'resource_semantics':'TELEMETRY_ONLY_FOR_HISTORICAL_TERMINAL_RESOLUTION; existing new-work admission guards unchanged',
                'planned_result':result,'powerloss_rename_namespace_durability_guaranteed':False}
            r.write_audit(audit/'resolution.json',resolution);r.fsync_dir(audit);r.fsync_dir(parent);r.fsync_dir(root)
            raw,identity=r.read_bound(root/'UNCERTAIN.json',b['marker_sha256'])
            if raw!=evidence['marker_raw'] or identity!=evidence['marker_identity']:raise Blocked('ORIGINAL_MARKER_CHANGED')
            info=os.fstat(lock_fd);live=os.stat(root/'generation.lock',follow_symlinks=False)
            if ((info.st_dev,info.st_ino)!=(live.st_dev,live.st_ino) or not stat.S_ISREG(live.st_mode)
                    or live.st_uid!=os.getuid() or stat.S_IMODE(live.st_mode)!=0o600 or live.st_nlink!=1):
                raise Blocked('COMMON_LOCK_CHANGED')
            # Commit only after the resolution and original bytes are durable.
            rename(root/'UNCERTAIN.json',archived);return result
        except BaseException as exc:
            exc.reconciliation_audit=str(audit)
            try:
                r.write_audit(audit/'failure.json',{'status':'BLOCKED_UNKNOWN_PRESERVED','stage':stage,
                    'error_class':type(exc).__name__,'reason':str(exc)[:512],'current_observation':current,
                    'traceback':traceback.format_exc(limit=8)[-6000:],'generation_requests':0})
                r.fsync_dir(audit)
            except Exception:pass
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group()
    mode.add_argument('--resolve-human-approved',action='store_true');mode.add_argument('--check-saved-evidence',action='store_true');a=p.parse_args()
    if not a.resolve_human_approved and not a.check_saved_evidence:
        print(json.dumps({'status':'PREPARED_ONLY_NO_ACTION','generation_requests':0,'container_mutations':0}));return 0
    if a.resolve_human_approved and APPROVAL_REQUEST=='PENDING_NOT_AUTHORIZED':raise Blocked('TERMINAL_RESOLUTION_APPROVAL_PENDING')
    if a.resolve_human_approved and (os.getuid()==0 or not sys.stdin.isatty()):raise Blocked('NORMAL_NONROOT_HOST_TTY_REQUIRED')
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':raise Blocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    modules={}
    for name,digest in SOURCES.items():
        path=here.with_name(name+'.py')
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise Blocked('PINNED_SOURCE_CHANGED')
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules[name]=module
    r=modules['reconcile_vllm_readiness'];h=modules['recover_router_postboot'];s=modules['reconcile_restored_swap']
    b=r.load_bindings(repo);evidence=r.validate_fixed_evidence(repo,b)
    integration=repo/'agents/local_llm/integration'
    for name,digest in h.SOURCE_SHA.items():r.read_bound(integration/name,digest,private=False)
    case=s.load_case(repo,r,b,h)
    if s.boot()!=case['boot_id']:raise Blocked('APPROVED_BOOT_CHANGED')
    if a.check_saved_evidence:
        print(json.dumps({'status':'FIXED_TERMINAL_CASE_SAVED_EVIDENCE_PASS','live_restoration':'NOT_CHECKED',
            'generation_requests':0,'container_mutations':0,'marker_changes':0}));return 0
    maintenance=h.pinned_import(integration/'host_router_maintenance.py','host_router_maintenance',h.SOURCE_SHA['host_router_maintenance.py'])
    c=r.ExistingReadOnlyCoordinator(repo,evidence['operator']);c.guard()
    m=maintenance.Maintenance(repo/'agents/local_llm',expected_existing_user=case['expected_user'])
    m.candidate={**json.loads(r.read_bound(r.runtime_for(repo)/'router-deployment.json',case['files']['router-deployment.json'])[0]),'human_deployment_confirmed':False}
    try:
        print('Resolving one terminal zero-generation-POST trial record. No start, generation, or resource admission decision.',file=sys.stderr,flush=True)
        print(json.dumps(resolve(repo,r,s,h,b,case,c,r.DockerReadOnly(c.guard),m)));return 0
    finally:m.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_AUTOMATIC_RETRY','error_class':type(exc).__name__,'reason':str(exc)[:512],
            'audit_directory':getattr(exc,'reconciliation_audit',None),'instruction':'Read audit; no automatic retry or model request.'}),file=sys.stderr)
        raise SystemExit(1)
