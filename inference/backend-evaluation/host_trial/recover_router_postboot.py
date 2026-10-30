"""Prepared human-host recovery of one existing owned router; no create/stop/remove."""
import argparse
import base64
import hashlib
import importlib
import json
import os
import re
from pathlib import Path
import stat
import sys
import time
import traceback
import uuid

RECONCILER_SHA='1488e529c34e0d1d554b1106dbb7edf226883991e45719ce26fc6ec1b2a0b4f5'
SOURCE_SHA={
    'host_router_maintenance.py':'8c0ca1018f403c99f64aaacfcb2122c6f4b6c27c9b29117fc9ab9ea7f86bb9aa',
    'host_deployment_check.py':'147c201257ab7950c39008c7131a3cf1a5767cf426fbc2dfeeda98d0ad3d06ec',
    'router-presets.PROPOSAL.ini':'36fb5b6da0b843adb7b1f9f20c9de44a33b77d9f070d3c73c5b143825314b465',
    'router-compose.PROPOSAL.yaml':'5df1f384ba494340c90dc98cc1762b02d58055695d4f9c3652d1fcf4f44704c1'}
INTENT='router-postboot-recovery-vllm-8949115c.intent.json'
USER_BINDINGS='router-existing-user-vllm-8949115c.json'
USER_BINDINGS_SHA='acf05dcdb7b8961acd1118feb3341a18e297a40ba2d161c7cd49df8a3842ea97'
CONTRACT_FIELDS={'container_id','image','name','compose_project_label','deployment_label','memory',
    'memory_swap','cpu','pids','readonly','privileged_false','cap_drop','cap_add','no_new_privileges',
    'port_bindings','user','entrypoint','argv','network_names','mount_destinations','mount_contract'}


class RecoveryBlocked(RuntimeError):pass


def exception_code(exc):
    value=getattr(exc,'code',None)
    if not isinstance(value,str):value=str(exc)
    return value if value.isupper() and value.replace('_','').isalnum() else 'UNCLASSIFIED_EXCEPTION'


def typed_equal(value,expected):
    return (isinstance(value,dict) and set(value)==set(expected)
        and all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()))


def load_existing_user(repo,r,b):
    """One fixed existing CID/user, proven by immutable readonly diagnostic bytes."""
    root=r.runtime_for(repo)
    d=json.loads(r.read_bound(root/USER_BINDINGS,USER_BINDINGS_SHA)[0])
    state=json.loads(r.read_bound(root/'router-host-state.json',r.DIAG_STATE_SHA)[0])
    r.read_bound(root/'router-deployment.json',r.DIAG_ROUTE_SHA)
    user=d.get('expected_user')
    if (type(d.get('schema')) is not int or d.get('schema')!=1 or d.get('purpose')!='fixed_existing_router_user_comparison_only'
            or d.get('run_name')!=b['run_name'] or d.get('profile_sha256')!=b['profile_sha256']
            or d.get('marker_sha256')!=b['marker_sha256'] or d.get('router_cid')!=state.get('router_cid')
            or d.get('state_sha256')!=r.DIAG_STATE_SHA or d.get('route_sha256')!=r.DIAG_ROUTE_SHA
            or not isinstance(user,str) or len(user)>32 or re.fullmatch('[1-9][0-9]*:[1-9][0-9]*',user) is None
            or int(user.split(':')[0])!=os.getuid()):
        raise RecoveryBlocked('FIXED_EXISTING_USER_BINDING_MISMATCH')
    directory=d.get('diagnostic_directory');source=d.get('source_evidence_directory')
    if (not isinstance(directory,str) or re.fullmatch('router-postboot-diagnostics-[0-9a-f]{32}',directory) is None
            or source!='router-user-evidence-vllm-8949115c'):
        raise RecoveryBlocked('FIXED_USER_EVIDENCE_PATH_MISMATCH')
    for name,digest in d['source_sha256'].items():
        if name not in {'host_router_maintenance.before.py','recover_router_postboot.before.py'}:
            raise RecoveryBlocked('FIXED_USER_SOURCE_EVIDENCE_MISMATCH')
        r.read_bound(root/source/name,digest)
    if set(d['source_sha256'])!={'host_router_maintenance.before.py','recover_router_postboot.before.py'}:
        raise RecoveryBlocked('FIXED_USER_SOURCE_EVIDENCE_MISSING')
    report=json.loads(r.read_bound(root/directory/'failure.json',d['diagnostic_sha256']['failure.json'])[0])
    started=json.loads(r.read_bound(root/directory/'started.json',d['diagnostic_sha256']['started.json'])[0])
    observed=report.get('observations',{});contract=observed.get('router_contract',{});matches=contract.get('matches',{})
    if (not typed_equal(started,{'mode':'readonly','run':b['run_name'],'marker_sha256':b['marker_sha256'],'automatic_retry':False})
            or report.get('error_code')!='ROUTER_CONTRACT_MISMATCH'
            or report.get('stage')!='verify_fixed_owned_router_contract'
            or report.get('diagnose_only') is not True or report.get('start_intent_exists') is not False
            or type(report.get('generation_requests')) is not int or report['generation_requests']!=0
            or not typed_equal(observed.get('original30b'),{'present':True,'running':False})
            or set(matches)!=CONTRACT_FIELDS or any(type(v) is not bool for v in matches.values())
            or matches.get('user') is not False or any(not v for k,v in matches.items() if k!='user')
            or contract.get('mismatches')!=['user'] or contract.get('container_user')!=user
            or not typed_equal(contract.get('state'),{'Status':'exited','Running':False,'Pid':0,'ExitCode':0,'OOMKilled':False})):
        raise RecoveryBlocked('FIXED_USER_ONLY_DIAGNOSTIC_NOT_PROVEN')
    return user


def contract_observation(m,value):
    """Only selected metadata/match flags; never raw labels, env, args or inspect."""
    if not isinstance(value,dict):return {'present':False}
    h=value.get('HostConfig',{});config=value.get('Config',{});labels=config.get('Labels',{})
    mounts={v.get('Destination'):v for v in value.get('Mounts',[]) if v.get('Type')=='bind'}
    expected_mounts={'/models':(str(m.repo/'models'),False),
        '/cache':(str(m.repo/'.cache/large-coder-b3/runtime'),True),
        '/config/models.ini':(str(m.llm/'integration/router-presets.PROPOSAL.ini'),False)}
    matches={
        'container_id':value.get('Id')==m.state.get('router_cid'),
        'image':value.get('Image')==m.profile.get('image'),
        'name':value.get('Name')=='/'+m.profile.get('router_name',''),
        'compose_project_label':labels.get('com.docker.compose.project')=='project-kiss-aceis-router',
        'deployment_label':labels.get('io.aceis.deployment')==m.state.get('token'),
        'memory':h.get('Memory')==34359738368,'memory_swap':h.get('MemorySwap')==34359738368,
        'cpu':h.get('NanoCpus')==8000000000,'pids':h.get('PidsLimit')==512,
        'readonly':h.get('ReadonlyRootfs') is True,'privileged_false':h.get('Privileged') is False,
        'cap_drop':h.get('CapDrop')==['ALL'],'cap_add':h.get('CapAdd') in (None,[]),
        'no_new_privileges':'no-new-privileges:true' in h.get('SecurityOpt',[]),
        'port_bindings':h.get('PortBindings')=={'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]},
        'user':config.get('User')==getattr(m,'expected_existing_user',str(os.getuid())+':'+str(os.getgid())),
        'entrypoint':value.get('Path')=='/app/llama-server',
        'argv':value.get('Args')==['--models-preset','/config/models.ini','--models-max','1','--no-models-autoload','--host','0.0.0.0','--port','8080','--offline','--no-ui'],
        'network_names':set(value.get('NetworkSettings',{}).get('Networks',{}))=={'project-kiss-large-coder-b3_local'},
        'mount_destinations':set(mounts)==set(expected_mounts),
        'mount_contract':set(mounts)==set(expected_mounts) and all((mounts[k].get('Source'),mounts[k].get('RW'))==v for k,v in expected_mounts.items())}
    # Only a bounded numeric UID:GID is safe to print; arbitrary User strings
    # could contain secrets in a modified object and are not echoed.
    observed_user=config.get('User');numeric=isinstance(observed_user,str) and len(observed_user)<=32 and all(c in '0123456789:' for c in observed_user)
    return {'present':True,'matches':matches,'mismatches':[k for k,v in matches.items() if not v],
        'container_user':observed_user if numeric else 'NON_NUMERIC_OR_MISSING',
        'expected_user':getattr(m,'expected_existing_user',str(os.getuid())+':'+str(os.getgid())),
        'current_user':str(os.getuid())+':'+str(os.getgid()),
        'state':{k:value.get('State',{}).get(k) for k in ('Status','Running','Pid','ExitCode','OOMKilled')}}


def pinned_import(path,name,digest):
    # No module execution until exact owner-regular source bytes match.
    p=Path(path)
    info=p.lstat()
    if (any(q.is_symlink() for q in [p,*p.parents]) or not stat.S_ISREG(info.st_mode)
            or info.st_uid!=os.getuid() or info.st_nlink!=1 or hashlib.sha256(p.read_bytes()).hexdigest()!=digest):
        raise RecoveryBlocked('FIXED_SOURCE_CHANGED')
    sys.path.insert(0,str(p.parent))
    return importlib.import_module(name)


def ensure_container_states(m):
    m.enter('verify_original30b_stopped');original,_=m.original()
    m.enter('verify_fixed_owned_router_contract');router=m.owned_router()
    if original.get('State',{}).get('Running') is not False:
        raise RecoveryBlocked('ORIGINAL30B_RUNNING_OR_UNKNOWN_NO_MUTATION')
    if not router or router.get('Id')!=m.state.get('router_cid'):
        raise RecoveryBlocked('FIXED_OWNED_ROUTER_MISSING_OR_CHANGED')
    state=router.get('State',{});running=state.get('Running')
    if (type(running) is not bool or state.get('Paused') is not False or state.get('Restarting') is not False
            or state.get('Dead') is not False or router.get('HostConfig',{}).get('RestartPolicy',{}).get('Name')!='no'
            or (not running and (state.get('Status') not in ('created','exited') or state.get('Pid')!=0))):
        raise RecoveryBlocked('ROUTER_STATE_OR_RESTART_POLICY_NOT_APPROVED')
    return router,running


def recover(repo,r,b,m,c,docker,diagnose_only=False):
    """Called only under the fixed host guard. Original UNKNOWN is never archived."""
    c.guard();root=r.runtime_for(repo)
    with r.reconciliation_lock(root):
        fixed=r.validate_fixed_evidence(repo,b)
        if (root/INTENT).exists() or (root/INTENT).is_symlink():raise RecoveryBlocked('RECOVERY_INTENT_EXISTS_NO_AUTOMATIC_RETRY')
        profile_raw,_=r.read_bound(root/'router-host-profile.json',b['profile_sha256'])
        route_raw,_=r.read_bound(root/'router-deployment.json',r.DIAG_ROUTE_SHA)
        state_raw,_=r.read_bound(root/'router-host-state.json',r.DIAG_STATE_SHA)
        profile=json.loads(profile_raw);route=json.loads(route_raw);state=json.loads(state_raw)
        if (m.state!=state or m.profile!=profile or state.get('phase')!='DEPLOYED'
                or route.get('container_id')!=state.get('router_cid') or route.get('image')!=profile.get('image')
                or route.get('network_id')!=profile.get('internal_network_id')
                or state.get('resident_cid')!=profile.get('resident_container_id')):
            raise RecoveryBlocked('FIXED_DEPLOYMENT_SCOPE_CHANGED')
        m.human_guard();c.daemon_observe();m.device_check();m.verify_preset()
        m.enter('verify_previous_trial_container_absent');docker.absent(b['container_id'],b['container_name'])
        m.enter('verify_preflight_resources')
        sample=c.c.rt._threshold(preflight=True)
        if sample.get('swap_used_bytes')!=0:raise RecoveryBlocked('SWAP_NONZERO_OR_UNKNOWN')
        m.enter('verify_fixed_internal_network');m.network(strict=True)
        m.enter('verify_existing_route_metadata');m.route_precheck()
        router,running=ensure_container_states(m)
        # Validate and preserve any pre-existing candidate through the existing gate.
        candidate=root/'router-candidate.json'
        candidate_raw=r.read_bound(candidate)[0] if candidate.exists() else None
        final=r.validate_fixed_evidence(repo,b)
        if final['marker_identity']!=fixed['marker_identity']:raise RecoveryBlocked('UNKNOWN_MARKER_CHANGED')
        if diagnose_only:
            return {'status':'READONLY_RECOVERY_PREFLIGHT_PASS','start_requests':0,'generation_requests':0,
                'container_mutations':0,'marker_changes':0,'router_running':running,'automatic_retry':False}
        # Durable before start: same fixed case gets at most one start intent.
        audit=root/('router-postboot-recovery-'+uuid.uuid4().hex);audit.mkdir(mode=0o700)
        r.write_audit(audit/'before.json',{'status':'FIXED_RECOVERY_PRECHECKS_PASSED','run':b['run_name'],
            'marker_sha256':b['marker_sha256'],'original_marker_base64':base64.b64encode(fixed['marker_raw']).decode(),
            'route_base64':base64.b64encode(route_raw).decode(),'state_base64':base64.b64encode(state_raw).decode(),
            'candidate_base64':base64.b64encode(candidate_raw).decode() if candidate_raw is not None else None,
            'router_id':router['Id'],'was_running':running,'resources':sample,'generation_requests':0})
        r.fsync_dir(audit);r.fsync_dir(root)
        r.write_audit(root/INTENT,{'status':'RECOVERY_INTENT_NO_RETRY','audit_directory':str(audit),
            'router_id':router['Id'],'start_limit':1,'generation_requests':0,'automatic_retry':False})
        r.fsync_dir(root)
        m.internal_route=True;m.recovery_deadline=time.monotonic()+180
        result={'status':'BLOCKED_AFTER_INTENT_NO_RETRY','audit_directory':str(audit),'start_requests':0,
            'generation_requests':0,'container_create_stop_remove':0,'marker_changes':0,'automatic_retry':False}
        try:
            # Last fixed CID/original stopped check immediately before the sole possible start.
            current,now_running=ensure_container_states(m)
            if current['Id']!=router['Id'] or now_running!=running:raise RecoveryBlocked('ROUTER_CHANGED_BEFORE_START')
            if not running:
                m.enter('postboot_start_existing_owned_router');m.save('START_ROUTER_INTENT')
                result['start_requests']=1  # This is an intent; a timeout is UNKNOWN, never resent.
                m.docker('start',router['Id'],timeout=30)
            original,_=m.original();current=m.owned_router()
            if original.get('State',{}).get('Running') is not False or not current or current.get('Id')!=router['Id'] or current.get('State',{}).get('Running') is not True:
                raise RecoveryBlocked('START_OR_ORIGINAL_STOPPED_NOT_CONFIRMED')
            m.network(strict=True)
            # Preserve old receipts before changing state endpoint/IP; otherwise existing
            # route_precheck would correctly reject the stale receipt after refresh.
            m.retire_routes();m.router_gate()
            observed=r.validate_current(c.observe())
            after=r.validate_fixed_evidence(repo,b)
            if after['marker_identity']!=fixed['marker_identity']:raise RecoveryBlocked('UNKNOWN_MARKER_CHANGED')
            result.update(status='OWNED_ROUTER_30B_READY_UNKNOWN_PRESERVED',current=observed,
                summary='UNKNOWN_PRESERVED',note='Run the separate fixed reconciliation only after reviewing this result.')
        except BaseException as exc:
            result['error_class']=type(exc).__name__
            code=getattr(exc,'code',None)
            if isinstance(code,str) and code.isupper() and code.replace('_','').isalnum():result['error_code']=code
            # No raw transport stderr/args/token and no automatic rollback/start retry.
            result['instruction']='Inspect actual router/route state and this audit; do not retry start or edit markers.'
            r.write_audit(audit/'terminal.json',result);r.fsync_dir(audit)
            raise
        r.write_audit(audit/'terminal.json',result);r.fsync_dir(audit)
        return result


def recover_and_reconcile(repo,r,b,m,c,docker):
    # Recovery closes its lock first; UNCERTAIN still blocks ordinary callers
    # during this gap. The original reconciler then obtains the same lock and
    # repeats all fixed evidence, absence and current-health checks itself.
    ready=recover(repo,r,b,m,c,docker)
    if ready.get('status')!='OWNED_ROUTER_30B_READY_UNKNOWN_PRESERVED':
        raise RecoveryBlocked('RECOVERY_NOT_READY_NO_RECONCILIATION')
    print('Router 30B ready; checking fixed UNKNOWN for audited archive.',file=sys.stderr,flush=True)
    archived=r.reconcile(repo,b,c,docker)
    return {'status':'EXISTING_ROUTER_RESTORED_AND_READINESS_RECONCILED',
        'recovery':ready,'reconciliation':archived,'generation_requests':0,
        'model_lifecycle_http_requests':0,'automatic_retry':False}


def run_audited(repo,r,b,m,c,docker,diagnose_only=False):
    """Records failures before start intent, without changing any guard."""
    c.guard();root=r.runtime_for(repo)
    audit=root/('router-postboot-diagnostics-'+uuid.uuid4().hex);audit.mkdir(mode=0o700)
    r.write_audit(audit/'started.json',{'mode':'readonly' if diagnose_only else 'recovery',
        'run':b['run_name'],'marker_sha256':b['marker_sha256'],'automatic_retry':False})
    r.fsync_dir(audit);r.fsync_dir(root)
    observations={};original_inspect=getattr(m,'inspect',None)
    def inspect(identity):
        value=original_inspect(identity)
        if identity in (m.profile['router_name'],m.state['router_cid']):
            try:observations['router_contract']=contract_observation(m,value)
            except Exception as exc:
                # Diagnostic collection must not replace the original guard's
                # behavior, even for malformed/null Docker metadata.
                observations['router_contract']={'observation_error_class':type(exc).__name__}
        elif identity==m.profile['resident_container_id']:
            observations['original30b']={'present':isinstance(value,dict),
                'running':value.get('State',{}).get('Running') if isinstance(value,dict) else None}
        return value
    if original_inspect is not None:m.inspect=inspect
    try:
        result=(recover(repo,r,b,m,c,docker,diagnose_only=True) if diagnose_only
            else recover_and_reconcile(repo,r,b,m,c,docker))
        if diagnose_only:
            result|={'audit_directory':str(audit),'observations':observations}
            r.write_audit(audit/'terminal.json',result);r.fsync_dir(audit)
        return result
    except BaseException as exc:
        report={'status':'BLOCKED_NO_AUTOMATIC_RETRY','error_class':type(exc).__name__,
            'error_code':exception_code(exc),'stage':getattr(m,'step','unknown'),
            'error_message':str(exc)[:512],'traceback':traceback.format_exc(limit=8)[-6000:],
            'observations':observations,'maintenance_log':str(getattr(m,'log_path','')),
            'start_intent_exists':(root/INTENT).exists(),'diagnose_only':diagnose_only,
            'generation_requests':0,'automatic_retry':False}
        exc.recovery_audit=str(audit)
        try:r.write_audit(audit/'failure.json',report);r.fsync_dir(audit)
        except Exception as audit_exc:exc.audit_write_error=type(audit_exc).__name__
        raise
    finally:
        if original_inspect is not None:m.inspect=original_inspect


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group()
    mode.add_argument('--recover-human-approved',action='store_true')
    mode.add_argument('--diagnose-human-readonly',action='store_true')
    mode.add_argument('--check-saved-evidence',action='store_true');args=p.parse_args()
    if not args.recover_human_approved and not args.diagnose_human_readonly and not args.check_saved_evidence:
        print(json.dumps({'status':'PREPARED_ONLY_NOT_EXECUTED','generation_requests':0,'container_mutations':0}));return 0
    if not args.check_saved_evidence and (os.getuid()==0 or not sys.stdin.isatty()):
        raise RecoveryBlocked('NORMAL_NONROOT_HOST_TTY_REQUIRED')
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':raise RecoveryBlocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    r=pinned_import(here.with_name('reconcile_vllm_readiness.py'),'reconcile_vllm_readiness',RECONCILER_SHA)
    b=r.load_bindings(repo);r.validate_fixed_evidence(repo,b)
    integration=repo/'agents/local_llm/integration'
    for name,digest in SOURCE_SHA.items():r.read_bound(integration/name,digest,private=False)
    maintenance=pinned_import(integration/'host_router_maintenance.py','host_router_maintenance',SOURCE_SHA['host_router_maintenance.py'])
    user=load_existing_user(repo,r,b)
    if args.check_saved_evidence:
        # Files and pure preset validation only. No constructor/log file, host
        # context guard, AF_UNIX, Docker, HTTP, model load or mutation.
        readonly=maintenance.Maintenance.__new__(maintenance.Maintenance)
        readonly.llm=repo/'agents/local_llm';readonly.enter=lambda step:None
        readonly.verify_preset()
        print(json.dumps({'status':'SAVED_EVIDENCE_AND_PRESET_PASS','expected_existing_user':user,
            'current_user':str(os.getuid())+':'+str(os.getgid()),'live_container_state':'NOT_CHECKED',
            'socket_requests':0,'generation_requests':0,'container_mutations':0,'marker_changes':0}));return 0
    operator=json.loads(r.read_bound(r.runtime_for(repo)/b['operator_name'],b['operator_sha256'])[0])
    c=r.ExistingReadOnlyCoordinator(repo,operator);c.guard()
    m=maintenance.Maintenance(repo/'agents/local_llm',expected_existing_user=user)
    try:
        print('Checking fixed router, stopped original, resources and common lock.',file=sys.stderr,flush=True)
        print(json.dumps(run_audited(repo,r,b,m,c,r.DockerReadOnly(c.guard),args.diagnose_human_readonly)));return 0
    finally:m.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as exc:
        if isinstance(exc,SystemExit):raise
        print(json.dumps({'status':'BLOCKED_NO_AUTOMATIC_RETRY','error_class':type(exc).__name__,'error_code':exception_code(exc),
            'audit_directory':getattr(exc,'recovery_audit',None),
            'audit_write_error':getattr(exc,'audit_write_error',None),
            'instruction':'Inspect host state and private recovery audit. No rollback or repeated start was attempted.'}),file=sys.stderr)
        raise SystemExit(1)
