"""Approved one-case residual-swap reconciliation. Never starts or generates."""
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

CASE_NAME='reconcile-restored-swap-vllm-8949115c.json'
CASE_SHA='dd300b4fed97f61435b0824a79bb8cfca5f3108c2d6cdcac4da808bbc9aea591'
RECONCILER_SHA='1488e529c34e0d1d554b1106dbb7edf226883991e45719ce26fc6ec1b2a0b4f5'
RECOVERY_SHA='708e5b770ec40b7a4433109099022b7eb672a6c710b31e4724521b62354a1571'
POLICY_SHA='e63b0595c006a32be61c1a6e04644b3aa4e335d8da49a3a0f6faececf5d3feda'
RECOVERY='router-postboot-recovery-5ff77a7215344f2d849be28f41724e4c'
DIAG='router-postboot-diagnostics-4f36d51cbbc3408abc6e08cf598828f7'
LOG='host-maintenance-20261030T110008Z-e4c880c3.jsonl'


class Blocked(RuntimeError):pass


def boot():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def vmstat():
    rows={k:int(v) for k,v in (line.split() for line in Path('/proc/vmstat').read_text().splitlines())}
    return {k:rows[k] for k in ('pswpin','pswpout')}


def typed(value,expected):
    return isinstance(value,dict) and set(value)==set(expected) and all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items())


def load_case(repo,r,b,h):
    root=r.runtime_for(repo);case=json.loads(r.read_bound(root/CASE_NAME,CASE_SHA)[0])
    if (case.get('purpose')!='one_fixed_postboot_residual_swap_reconciliation'
            or case.get('approval_request')!='Sentinel_7833ece37ab88191bd475f21930d6713'
            or case.get('run_name')!=b['run_name'] or case.get('profile_sha256')!=b['profile_sha256']
            or case.get('marker_sha256')!=b['marker_sha256'] or type(case.get('swap_baseline_bytes')) is not int
            or case['swap_baseline_bytes']!=577536):raise Blocked('FIXED_CASE_SCOPE_CHANGED')
    expected={'router-host-state.json','router-deployment.json','router-existing-user-vllm-8949115c.json',h.INTENT,
        RECOVERY+'/before.json',RECOVERY+'/terminal.json',DIAG+'/started.json',DIAG+'/failure.json',LOG}
    if set(case.get('files',{}))!=expected:raise Blocked('FIXED_CASE_FILES_CHANGED')
    raw={name:r.read_bound(root/name,digest)[0] for name,digest in case['files'].items()}
    data={name:json.loads(value) for name,value in raw.items() if name!=LOG}
    state=data['router-host-state.json'];route=data['router-deployment.json'];failure=data[DIAG+'/failure.json']
    intent=data[h.INTENT];before=data[RECOVERY+'/before.json'];terminal=data[RECOVERY+'/terminal.json']
    contract=failure.get('observations',{}).get('router_contract',{});matches=contract.get('matches',{})
    if (set(matches)!=h.CONTRACT_FIELDS or any(v is not True for v in matches.values())
            or contract.get('mismatches')!=[] or contract.get('container_user')!=case.get('expected_user')
            or failure.get('error_code')!='CURRENT_RESOURCES_NOT_RECONCILABLE'
            or failure.get('start_intent_exists') is not True or failure.get('diagnose_only') is not False
            or type(failure.get('generation_requests')) is not int or failure['generation_requests']!=0
            or not typed(failure.get('observations',{}).get('original30b'),{'present':True,'running':False})
            or not typed(terminal,{'status':'BLOCKED_AFTER_INTENT_NO_RETRY','audit_directory':str(root/RECOVERY),
                'start_requests':1,'generation_requests':0,'container_create_stop_remove':0,'marker_changes':0,
                'automatic_retry':False,'error_class':'Blocked','instruction':'Inspect actual router/route state and this audit; do not retry start or edit markers.'})
            or intent.get('router_id')!=case.get('router_cid') or intent.get('start_limit')!=1
            or intent.get('audit_directory')!=str(root/RECOVERY) or intent.get('automatic_retry') is not False
            or before.get('marker_sha256')!=b['marker_sha256'] or before.get('router_id')!=case.get('router_cid')
            or before.get('was_running') is not False or before.get('resources',{}).get('swap_used_bytes')!=0
            or state.get('phase')!='DEPLOYED' or state.get('router_cid')!=case.get('router_cid')
            or route.get('container_id')!=case.get('router_cid') or route.get('human_deployment_confirmed') is not True):
        raise Blocked('FIXED_SUCCESSFUL_START_AND_RESOURCE_ONLY_FAILURE_NOT_PROVEN')
    events=[json.loads(line) for line in raw[LOG].decode().splitlines()]
    gates=[]
    for event in events:
        if event.get('step')=='readonly_router_gate' and event.get('event')=='diagnostic':
            gates.append(json.loads(event['text']))
    starts=[v for v in events if v.get('step')=='postboot_start_existing_owned_router' and v.get('event')=='begin']
    if (len(starts)!=1 or len(gates)!=1 or gates[0].get('status')!='READONLY_GATE_PASS'
            or gates[0].get('router_models')!=r.STATES or gates[0].get('resources',{}).get('swap_used_bytes')!=577536
            or gates[0].get('generation_requests')!=0 or gates[0].get('lifecycle_operations')!=0):
        raise Blocked('FIXED_ONE_START_GATE_EVIDENCE_CHANGED')
    return case


def validate_ready(observed,r,baseline):
    # The existing zero-swap validator is untouched. This approved case retains
    # its exact model/slot/RAM/GPU contract and requires exact bound swap bytes.
    props=observed.get('properties') or {};slots=observed.get('slots');resource=observed.get('resources') or {}
    if (observed.get('models')!=r.STATES or observed.get('health',{}).get('status')!='ok'
            or props.get('model_alias')!=r.MODEL or type(props.get('total_slots')) is not int or props['total_slots']!=1
            or type(props.get('default_generation_settings',{}).get('n_ctx')) is not int
            or props['default_generation_settings']['n_ctx']!=32768 or not isinstance(slots,list)
            or len(slots)!=1 or slots[0].get('is_processing') is not False):raise Blocked('CURRENT_30B_CONTRACT_NOT_READY')
    if (any(type(resource.get(k)) is not int or resource[k]<0 for k in ('available_bytes','gpu_used_bytes','swap_used_bytes'))
            or resource['available_bytes']<24*(1<<30) or resource['gpu_used_bytes']>58*(1<<30)
            or resource['swap_used_bytes']!=baseline):raise Blocked('CURRENT_FIXED_RESOURCE_CONTRACT_CHANGED')
    return observed


def verify_live(m,case):
    m.human_guard();m.verify_preset();m.route_precheck()
    original,_=m.original();router=m.owned_router();state=router.get('State',{}) if router else {}
    if (original.get('State',{}).get('Running') is not False or not router or router.get('Id')!=case['router_cid']
            or state.get('Running') is not True or state.get('Status')!='running'
            or any(state.get(k) is not False for k in ('Paused','Restarting','Dead','OOMKilled'))
            or type(state.get('Pid')) is not int or state['Pid']<=0
            or router.get('HostConfig',{}).get('RestartPolicy',{}).get('Name')!='no'):
        raise Blocked('CURRENT_FIXED_ROUTER_OR_ORIGINAL_STATE_CHANGED')
    # Existing verify_only branch performs no save, route update or HTTP POST.
    m.capture_internal_route(verify_only=True)


def reconcile_case(repo,r,h,b,case,c,docker,m,policy,*,clock=time.monotonic,sleep=time.sleep,
                   read_boot=boot,read_vmstat=vmstat,rename=os.rename):
    c.guard();root=r.runtime_for(repo)
    with r.reconciliation_lock(root) as lock_fd:
        evidence=r.validate_fixed_evidence(repo,b)
        if load_case(repo,r,b,h)!=case:raise Blocked('CALLER_CASE_NOT_FIXED_BINDING')
        parent=root/'readiness-reconciliation-audits'
        if parent.exists():
            r.safe(parent);s=parent.stat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:raise Blocked('AUDIT_ROOT_UNSAFE')
        else:parent.mkdir(mode=0o700)
        audit=parent/(b['run_name']+'-restored-'+uuid.uuid4().hex);audit.mkdir(mode=0o700)
        r.write_audit(audit/'started.json',{'status':'FIXED_RESTORED_CASE_VALIDATED','approval':case['approval_request'],
            'marker_sha256':b['marker_sha256'],'generation_requests':0,'container_mutations':0})
        r.fsync_dir(audit);r.fsync_dir(parent)
        stage='initial_live_checks';steady=None;current=None;last_sample=None
        try:
            if read_boot()!=case['boot_id']:raise Blocked('APPROVED_BOOT_CHANGED')
            verify_live(m,case);c.daemon_observe()
            absent=docker.absent(b['container_id'],b['container_name'])
            current=validate_ready(c.observe(),r,case['swap_baseline_bytes'])
            stage='ten_second_fixed_swap_and_io_observation'
            steady=policy.FixedSteadySwap(case['boot_id'],case['swap_baseline_bytes']);started=clock()
            def sample():
                nonlocal last_sample
                last_sample={'elapsed':clock()-started,'boot_id':read_boot(),'resources':c.c.rt.probe(),'vmstat':read_vmstat()}
                steady.sample(last_sample['elapsed'],last_sample['boot_id'],last_sample['resources'],last_sample['vmstat'])
            sample();first=steady.samples[0]['elapsed']
            while steady.samples[-1]['elapsed']-first<10:
                sleep(2);sample()
            steady.finish()
            stage='final_live_identity_health_absence_checks'
            verify_live(m,case);c.daemon_observe();current=validate_ready(c.observe(),r,case['swap_baseline_bytes'])
            absent_after=docker.absent(b['container_id'],b['container_name'])
            final=r.validate_fixed_evidence(repo,b)
            if load_case(repo,r,b,h)!=case:raise Blocked('FIXED_CASE_CHANGED_BEFORE_COMMIT')
            if final['marker_identity']!=evidence['marker_identity']:raise Blocked('UNKNOWN_MARKER_REPLACED')
            sample();proof=steady.finish();stage='durable_audit_before_archive'
            archived=audit/'UNCERTAIN.original.json'
            result={'status':'RECONCILED_FIXED_RESTORED_SWAP_NO_GENERATION','audit_directory':str(audit),
                'archived_marker':str(archived),'original_summary':'UNKNOWN_PRESERVED','vllm_consumed_attempt_preserved':True,
                'generation_requests':0,'model_lifecycle_requests':0,'container_mutations':0,'automatic_retry':False}
            r.write_audit(audit/'audit.json',{'status':'ALL_FIXED_READONLY_PROBES_PASSED_ARCHIVE_AUTHORIZED',
                'case':case,'original_marker_base64':base64.b64encode(evidence['marker_raw']).decode(),
                'original_marker_parsed':evidence['marker'],'summary_sha256':evidence['summary_sha256'],
                'consumed_attempt_sha256':evidence['attempt_sha256'],'swap_stability':proof,
                'docker_absence_before':absent,'docker_absence_after':absent_after,'current_readonly_observations':current,
                'planned_result':result,'powerloss_rename_namespace_durability_guaranteed':False})
            r.fsync_dir(audit);r.fsync_dir(parent);r.fsync_dir(root)
            # Fresh sample immediately before commit; preserve it durably too.
            stage='precommit_resource_and_marker_check';sample()
            r.write_audit(audit/'precommit.json',{'swap_stability':steady.finish(),'stage':stage});r.fsync_dir(audit)
            if clock()-started-steady.samples[-1]['elapsed']>5:raise Blocked('PRECOMMIT_RESOURCE_EVIDENCE_STALE')
            raw,identity=r.read_bound(root/'UNCERTAIN.json',b['marker_sha256'])
            if identity!=evidence['marker_identity'] or raw!=evidence['marker_raw']:raise Blocked('UNKNOWN_MARKER_CHANGED_BEFORE_ARCHIVE')
            info=os.fstat(lock_fd);live=os.stat(root/'generation.lock',follow_symlinks=False)
            if ((info.st_dev,info.st_ino)!=(live.st_dev,live.st_ino) or not stat.S_ISREG(live.st_mode)
                    or live.st_uid!=os.getuid() or stat.S_IMODE(live.st_mode)!=0o600 or live.st_nlink!=1):raise Blocked('GENERATION_LOCK_CHANGED')
            # Commit point. No fallible write/probe follows it.
            rename(root/'UNCERTAIN.json',archived);return result
        except BaseException as exc:
            exc.reconciliation_audit=str(audit)
            try:
                r.write_audit(audit/'failure.json',{'status':'BLOCKED_UNKNOWN_PRESERVED','stage':stage,
                    'error_class':type(exc).__name__,'reason':str(exc)[:512],'traceback':traceback.format_exc(limit=8)[-6000:],
                    'current_observation':current,'samples':steady.samples if steady else [],
                    'last_attempted_sample':last_sample,'generation_requests':0})
                r.fsync_dir(audit)
            except Exception:pass
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group()
    mode.add_argument('--reconcile-human-approved',action='store_true');mode.add_argument('--check-saved-evidence',action='store_true');a=p.parse_args()
    if not a.reconcile_human_approved and not a.check_saved_evidence:
        print(json.dumps({'status':'PREPARED_ONLY_NO_ACTION','generation_requests':0,'container_mutations':0}));return 0
    if not a.check_saved_evidence and (os.getuid()==0 or not sys.stdin.isatty()):raise Blocked('NORMAL_NONROOT_HOST_TTY_REQUIRED')
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':raise Blocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    # Pin recognized local modules before executing their import bodies.
    def load(name,digest):
        path=here.with_name(name+'.py');raw=path.read_bytes()
        if path.is_symlink() or hashlib.sha256(raw).hexdigest()!=digest:raise Blocked('PINNED_SOURCE_CHANGED')
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    r=load('reconcile_vllm_readiness',RECONCILER_SHA);h=load('recover_router_postboot',RECOVERY_SHA);policy=load('stable_swap_policy',POLICY_SHA)
    b=r.load_bindings(repo);evidence=r.validate_fixed_evidence(repo,b)
    integration=repo/'agents/local_llm/integration'
    for name,digest in h.SOURCE_SHA.items():r.read_bound(integration/name,digest,private=False)
    case=load_case(repo,r,b,h)
    if boot()!=case['boot_id']:raise Blocked('APPROVED_BOOT_CHANGED')
    if a.check_saved_evidence:
        print(json.dumps({'status':'FIXED_RESTORED_SWAP_SAVED_EVIDENCE_PASS','swap_baseline_bytes':case['swap_baseline_bytes'],
            'live_stability':'NOT_CHECKED','generation_requests':0,'container_mutations':0,'marker_changes':0}));return 0
    maintenance=h.pinned_import(integration/'host_router_maintenance.py','host_router_maintenance',h.SOURCE_SHA['host_router_maintenance.py'])
    c=r.ExistingReadOnlyCoordinator(repo,evidence['operator']);c.guard()
    m=maintenance.Maintenance(repo/'agents/local_llm',expected_existing_user=case['expected_user'])
    m.candidate={**json.loads(r.read_bound(r.runtime_for(repo)/'router-deployment.json',case['files']['router-deployment.json'])[0]),'human_deployment_confirmed':False}
    try:
        print('Read-only reconciliation: fixed router already running; observing10seconds. No start or generation.',file=sys.stderr,flush=True)
        print(json.dumps(reconcile_case(repo,r,h,b,case,c,r.DockerReadOnly(c.guard),m,policy)));return 0
    finally:m.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_AUTOMATIC_RETRY','error_class':type(exc).__name__,'reason':str(exc)[:512],
            'audit_directory':getattr(exc,'reconciliation_audit',None),'instruction':'Read saved audit; do not restart router or issue model requests.'}),file=sys.stderr)
        raise SystemExit(1)
