"""One fixed readiness-only UNKNOWN reconciliation; no model/container mutation."""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid

BINDINGS_SHA='1198b95c092a8fab31a34b998c68dfc43dff6fec22256313bc8acb68a729515c'
BINDINGS_NAME='reconcile-readiness-bindings-vllm-8949115c.json'
DIAG_ROUTE_SHA='89c464119551929e7a8a63039dd5c1ca7b2e178db1c5b283d6a0de1c8076e90b'
DIAG_STATE_SHA='7be1b1c22697df5e6bdf7f58734dc3f5baa0aae7fee4e5476040b73046e7abe5'
MODEL='kiss-qwen3-coder-30b'
STATES={'kiss-b3-gpt-oss-120b':'unloaded','kiss-b3-qwen-coder-next':'unloaded',MODEL:'loaded'}
CODE='NEXT_API_TRIAL_OUTCOME_UNKNOWN_NO_RETRY'
REASON='Unknown:HTTP_STAGE_DEADLINE_BEFORE_SEND'


class Blocked(RuntimeError):pass


def safe(path):
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts or any(q.is_symlink() for q in [p,*p.parents]):
        raise Blocked('UNSAFE_FIXED_PATH')
    return p


def read_bound(path,digest=None,private=True):
    p=safe(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1
                or info.st_size>2*1024*1024 or (private and stat.S_IMODE(info.st_mode)!=0o600)):
            raise Blocked('UNSAFE_BOUND_FILE')
        raw=f.read(2*1024*1024+1)
    if len(raw)>2*1024*1024 or (digest is not None and hashlib.sha256(raw).hexdigest()!=digest):
        raise Blocked('FIXED_EVIDENCE_HASH_MISMATCH')
    return raw,(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)


def load_bindings(repo):
    raw,_=read_bound(runtime_for(repo)/BINDINGS_NAME,BINDINGS_SHA,private=True)
    return json.loads(raw)


def runtime_for(repo):
    root=safe(Path(repo)/'agents/local_llm/.runtime');s=root.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
        raise Blocked('OWNER_ONLY_EXISTING_RUNTIME_REQUIRED')
    return root


@contextmanager
def reconciliation_lock(runtime):
    """Fixed reconciliation only; normal Client.locked remains unchanged."""
    path=safe(Path(runtime)/'generation.lock')
    # Must already exist. Do not create/replace the common lock or change its mode.
    fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid()
                or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1):
            raise Blocked('EXISTING_GENERATION_LOCK_UNSAFE')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Blocked('GENERATION_LOCK_BUSY') from None
        current=os.stat(path,follow_symlinks=False)
        if (current.st_dev,current.st_ino)!=(s.st_dev,s.st_ino):raise Blocked('GENERATION_LOCK_REPLACED')
        yield fd
    finally:os.close(fd)


def assert_no_request_files(run):
    for name in ['request.json','post-intent.json','response.json']:
        p=Path(run)/name
        if p.exists() or p.is_symlink():raise Blocked('REQUEST_OR_POST_EVIDENCE_EXISTS_NO_RECONCILE')


def validate_fixed_evidence(repo,bindings):
    rt=runtime_for(repo);run=rt/'backend-api-trials'/bindings['run_name']
    for rel,digest in bindings['code_files'].items():read_bound(Path(repo)/rel,digest,private=False)
    operator_raw,_=read_bound(rt/bindings['operator_name'],bindings['operator_sha256'])
    operator=json.loads(operator_raw)
    if (operator.get('project_root')!=str(Path(repo))
            or operator.get('coordinator_runtime_relative')!=bindings['coordinator_runtime_relative']
            or operator.get('model_dir')!=str(Path(repo)/'models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c')):
        raise Blocked('FIXED_OPERATOR_SCOPE_MISMATCH')
    profile_raw,_=read_bound(rt/'router-host-profile.json',bindings['profile_sha256'])
    marker_raw,marker_identity=read_bound(rt/'UNCERTAIN.json',bindings['marker_sha256'])
    marker=json.loads(marker_raw)
    if set(marker)!={'code','time','automatic_retry'} or marker.get('code')!=CODE or marker.get('automatic_retry') is not False:
        raise Blocked('OTHER_UNKNOWN_MARKER_NOT_RECONCILABLE')
    data={};file_hashes={}
    for name,digest in bindings['run_files'].items():
        raw,_=read_bound(run/name,digest);data[name]=json.loads(raw);file_hashes[name]=digest
    summary=data['summary.json']
    expected={'status':'UNKNOWN','backend':'vllm','environment':'FAIL','quality':'UNASSESSED',
        'generation_requests':0,'generation_request_intents':0,'generation_uncertain':False,
        'cleanup_confirmed':True,'source_metadata_unchanged':True,'automatic_retry':False,
        'code_executed':False,'reason':REASON}
    if any(type(summary.get(k)) is not type(v) or summary.get(k)!=v for k,v in expected.items()):
        raise Blocked('ONLY_FIXED_READINESS_ZERO_POST_UNKNOWN_ALLOWED')
    restoration=summary.get('restoration') or {}
    if restoration.get('status')!='RESTORED' or restoration.get('model_states')!=STATES:
        raise Blocked('SAVED_30B_RESTORATION_NOT_CONFIRMED')
    identity=data['identity.json'];route=data['temporary-route.json'];logs=data['server-log-tail.json']
    cid=bindings['container_id'];name=bindings['container_name']
    if (identity.get('name')!=name or identity.get('owner')!=str(os.getuid())
            or route.get('container_id')!=cid or logs.get('container_id')!=cid
            or logs.get('terminal_before_read') is not True):
        raise Blocked('RUN_CONTAINER_IDENTITY_EVIDENCE_MISMATCH')
    events=[v for k,v in data.items() if k.startswith('event-')]
    starts=[v for v in events if v.get('event')=='start_owned_intent']
    terminals=[v for v in events if v.get('event')=='owned_container_terminal']
    creates=[v for v in events if v.get('event')=='create_owned_intent']
    if (len(starts)!=1 or starts[0].get('cid')!=cid or len(terminals)!=1
            or terminals[0].get('cid')!=cid or terminals[0].get('state')!='exited'
            or len(creates)!=1 or creates[0].get('name')!=name):
        raise Blocked('START_ROUTE_LOG_TERMINAL_CID_NOT_ONE_FIXED_CONTAINER')
    attempt=rt/'backend-api-trials'/('attempt-vllm-'+bindings['operator_sha256']+'.json')
    attempt_raw,_=read_bound(attempt);attempt_data=json.loads(attempt_raw)
    if attempt_data!={'backend':'vllm','operator_sha256':bindings['operator_sha256'],'run':str(run),
                      'attempt_limit':1,'generation_request_limit':1,'automatic_retry':False}:
        raise Blocked('CONSUMED_ATTEMPT_MISMATCH')
    assert_no_request_files(run)
    return {'operator':operator,'marker_raw':marker_raw,'marker':marker,'marker_identity':marker_identity,
        'summary_sha256':file_hashes['summary.json'],'run_file_sha256':file_hashes,
        'profile_sha256':hashlib.sha256(profile_raw).hexdigest(),'attempt_sha256':hashlib.sha256(attempt_raw).hexdigest()}


class DockerReadOnly:
    def __init__(self,guard):self.guard=guard
    def absent(self,cid,name):
        observations=[]
        for kind,value in [('id',cid),('name','^/'+name+'$')]:
            self.guard()
            r=subprocess.run(['/usr/bin/docker','--host','unix:///var/run/docker.sock','container','ls',
                '-a','--no-trunc','--filter',kind+'='+value,'--format','{{.ID}}'],
                capture_output=True,text=True,timeout=10,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            if r.returncode or len(r.stdout)>65536:raise Blocked('DOCKER_READ_UNAVAILABLE_NO_PRIVILEGE_RETRY')
            if r.stdout.strip():raise Blocked('FIXED_CONTAINER_OR_NAME_STILL_PRESENT')
            observations.append({'filter':kind,'fixed_value':value,'observed_ids':[]})
        return observations


class ExistingReadOnlyCoordinator:
    def __init__(self,repo,operator):
        helpers=Path(repo)/'inference/backend-evaluation/host_trial';sys.path.insert(0,str(helpers))
        import host_strata_trial as h
        self.h=h;self.c=h.Coordinator(repo,operator)
    def guard(self):return self.c.guard()
    def daemon_observe(self):
        self.guard()
        from control_socket import request
        data=request(self.c.control_root,'status',timeout=5)
        self.h.require_idle_status(data,self.c.control_root)
        return {k:data[k] for k in ('paused','stopping','task_counts')}|{'idle':True}
    def observe(self):
        original=self.c.rt.read;stage='coordinator_idle'
        def annotated(path,end):
            try:return original(path,end)
            except Exception as exc:
                # No exception message/body/URL: only fixed caller path and class/code.
                code=getattr(exc,'code',None)
                suffix=':'+code if isinstance(code,str) and code.isupper() and code.replace('_','').isalnum() else ''
                raise Blocked('READ_STAGE:'+stage+':GET:'+path+':'+type(exc).__name__+suffix) from None
        self.c.rt.read=annotated
        try:
            try:states=self.c.idle()  # Same existing checks; no c.locked().
            except Blocked:raise
            except Exception as exc:raise Blocked('READ_STAGE:coordinator_idle_pre_or_between_GET:'+type(exc).__name__) from None
            stage='resident_confirmation';end=time.monotonic()+15
            return {'models':states,'health':self.c.rt.read('/health',end),
                'properties':self.c.rt.read('/props?model='+MODEL+'&autoload=false',end),
                'slots':self.c.rt.read('/slots?model='+MODEL+'&autoload=false',end),
                'resources':self.c.rt._threshold(preflight=True)}
        finally:self.c.rt.read=original


def inspect_fixed_container(cid,guard):
    """Normal-human Docker read only; formatted fields exclude env, args, mounts."""
    if not isinstance(cid,str) or len(cid)!=64 or any(c not in '0123456789abcdef' for c in cid):
        raise Blocked('FIXED_CONTAINER_ID_INVALID')
    guard()
    template='{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},"state":{{json .State.Running}},"status":{{json .State.Status}},"pid":{{json .State.Pid}},"exit_code":{{json .State.ExitCode}},"oom":{{json .State.OOMKilled}},"restart_policy":{{json .HostConfig.RestartPolicy.Name}},"networks":{{json .NetworkSettings.Networks}}}'
    result=subprocess.run(['/usr/bin/docker','--host','unix:///var/run/docker.sock','container','inspect',
        '--format',template,cid],capture_output=True,text=True,timeout=10,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if result.returncode or len(result.stdout)>65536:raise Blocked('DOCKER_INSPECT_READ_UNAVAILABLE_NO_PRIVILEGE_RETRY')
    data=json.loads(result.stdout)
    if data.get('id')!=cid:raise Blocked('INSPECT_CONTAINER_ID_MISMATCH')
    data['networks']={name:{k:net.get(k) for k in ('NetworkID','EndpointID','IPAddress','Gateway')}
        for name,net in data.get('networks',{}).items()}
    return data


def diagnose(repo,bindings,coordinator,inspect=inspect_fixed_container):
    """Observe only. Never calls reconcile/archive or any lifecycle method."""
    coordinator.guard();rt=runtime_for(repo)
    with reconciliation_lock(rt):
        evidence=validate_fixed_evidence(repo,bindings)
        profile=json.loads(read_bound(rt/'router-host-profile.json',bindings['profile_sha256'])[0])
        route=json.loads(read_bound(rt/'router-deployment.json',DIAG_ROUTE_SHA)[0])
        state=json.loads(read_bound(rt/'router-host-state.json',DIAG_STATE_SHA)[0])
        if (route.get('container_id')!=state.get('router_cid') or state.get('resident_cid')!=profile.get('resident_container_id')
                or route.get('image')!=profile.get('image') or route.get('network_id')!=profile.get('internal_network_id')
                or route.get('ipv4')!=state.get('route_ipv4') or route.get('endpoint_id')!=state.get('route_endpoint_id')
                or route.get('port')!=8080 or state.get('phase')!='DEPLOYED'):
            raise Blocked('DIAGNOSTIC_FIXED_ROUTE_STATE_MISMATCH')
        result={'status':'READONLY_DIAGNOSIS_NO_RECOVERY','generation_requests':0,'model_lifecycle_requests':0,
            'container_mutations':0,'marker_changes':0,'automatic_retry':False,'observations':{}}
        def probe(name,fn):
            before=time.monotonic()
            try:value={'ok':True,'data':fn()}
            except Exception as exc:
                value={'ok':False,'error_class':type(exc).__name__}
                if isinstance(exc,Blocked):value['reason']=str(exc)
            value['seconds']=round(time.monotonic()-before,3);result['observations'][name]=value
        def router():
            data=inspect(route['container_id'],coordinator.guard)
            net=data['networks'].get(route['network_name'],{})
            data['receipt_matches']={'name':data.get('name')=='/'+profile['router_name'],
                'image':data.get('image')==route['image'],'network_id':net.get('NetworkID')==route['network_id'],
                'ipv4':net.get('IPAddress')==route['ipv4'],'endpoint_id':net.get('EndpointID')==route['endpoint_id']}
            return data
        probe('router_container',router)
        probe('original30b_container',lambda:inspect(profile['resident_container_id'],coordinator.guard))
        probe('daemon_status',coordinator.daemon_observe)
        probe('router_and_resident_reads',coordinator.observe)
        final=validate_fixed_evidence(repo,bindings)
        if final['marker_identity']!=evidence['marker_identity']:raise Blocked('UNKNOWN_MARKER_REPLACED')
        result['original_marker_sha256']=bindings['marker_sha256'];result['original_summary']='UNKNOWN_PRESERVED'
        return result


def validate_current(observed):
    if observed.get('models')!=STATES or observed.get('health',{}).get('status')!='ok':
        raise Blocked('CURRENT_30B_ONLY_HEALTH_NOT_CONFIRMED')
    props=observed.get('properties') or {};context=props.get('default_generation_settings',{}).get('n_ctx')
    if (props.get('model_alias')!=MODEL or type(context) is not int or context!=32768
            or type(props.get('total_slots')) is not int or props['total_slots']!=1):
        raise Blocked('CURRENT_30B_PROFILE_CHANGED')
    slots=observed.get('slots')
    if not isinstance(slots,list) or len(slots)!=1 or slots[0].get('is_processing') is not False:
        raise Blocked('CURRENT_SLOT_BUSY_OR_UNKNOWN')
    r=observed.get('resources') or {}
    if any(type(r.get(k)) is not int for k in ['available_bytes','gpu_used_bytes','swap_used_bytes']):
        raise Blocked('CURRENT_RESOURCE_EVIDENCE_UNAVAILABLE')
    if r['available_bytes']<24*(1<<30) or r['gpu_used_bytes']>58*(1<<30) or r['swap_used_bytes']!=0:
        raise Blocked('CURRENT_RESOURCES_NOT_RECONCILABLE')
    return observed


def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def write_audit(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as out:
        json.dump(value,out,indent=2);out.flush();os.fsync(out.fileno())


def reconcile(repo,bindings,coordinator,docker,*,rename=os.rename):
    coordinator.guard();rt=runtime_for(repo)
    with reconciliation_lock(rt) as lock_fd:
        evidence=validate_fixed_evidence(repo,bindings)
        absent=docker.absent(bindings['container_id'],bindings['container_name'])
        current=validate_current(coordinator.observe())
        # Recheck both immutable CID and fixed name after API observations.
        absent_after=docker.absent(bindings['container_id'],bindings['container_name'])
        final=validate_fixed_evidence(repo,bindings)
        if final['marker_identity']!=evidence['marker_identity']:raise Blocked('UNKNOWN_MARKER_REPLACED')
        parent=rt/'readiness-reconciliation-audits'
        if parent.exists():
            safe(parent);s=parent.stat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
                raise Blocked('AUDIT_ROOT_UNSAFE')
        else:parent.mkdir(mode=0o700)
        audit=parent/(bindings['run_name']+'-'+uuid.uuid4().hex);audit.mkdir(mode=0o700)
        archived=audit/'UNCERTAIN.original.json'
        result={'status':'RECONCILED_READINESS_ONLY_NO_GENERATION','audit_directory':str(audit),
                'archived_marker':str(archived),'original_summary':'UNKNOWN_PRESERVED',
                'vllm_consumed_attempt_preserved':True,'automatic_retry':False,
                'generation_requests':0,'model_lifecycle_requests':0,'container_mutations':0}
        audit_data={'status':'ALL_READONLY_PROBES_PASSED_ARCHIVE_AUTHORIZED','prepared_at_unix':time.time(),
            'run':bindings['run_name'],'fixed_bindings':bindings,'marker_sha256':bindings['marker_sha256'],
            'original_marker_base64':base64.b64encode(evidence['marker_raw']).decode(),
            'original_marker_parsed':evidence['marker'],'summary_sha256':evidence['summary_sha256'],
            'summary_status_preserved':'UNKNOWN','consumed_attempt_sha256':evidence['attempt_sha256'],
            'docker_absence_before':absent,'docker_absence_after':absent_after,'current_readonly_observations':current,
            'planned_result':result,'powerloss_rename_namespace_durability_guaranteed':False}
        write_audit(audit/'audit.json',audit_data)
        fsync_dir(audit);fsync_dir(parent);fsync_dir(rt)
        # Last fallible operation before commit: verify the exact original marker.
        raw,identity=read_bound(rt/'UNCERTAIN.json',bindings['marker_sha256'])
        if identity!=evidence['marker_identity'] or raw!=evidence['marker_raw']:
            raise Blocked('UNKNOWN_MARKER_CHANGED_BEFORE_ARCHIVE')
        lock_info=os.fstat(lock_fd);lock_path_info=os.stat(rt/'generation.lock',follow_symlinks=False)
        if ((lock_info.st_dev,lock_info.st_ino)!=(lock_path_info.st_dev,lock_path_info.st_ino)
                or not stat.S_ISREG(lock_path_info.st_mode) or lock_path_info.st_uid!=os.getuid()
                or stat.S_IMODE(lock_path_info.st_mode)!=0o600 or lock_path_info.st_nlink!=1):
            raise Blocked('GENERATION_LOCK_CHANGED_BEFORE_ARCHIVE')
        # Atomic rename is the commit point, not deletion. No fallible post-commit
        # probe/write/fsync is attempted. Durable audit already contains raw bytes.
        rename(rt/'UNCERTAIN.json',archived)
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group()
    mode.add_argument('--reconcile-human-approved',action='store_true');mode.add_argument('--diagnose-human-readonly',action='store_true');a=p.parse_args()
    if not a.reconcile_human_approved and not a.diagnose_human_readonly:
        print(json.dumps({'status':'PREPARED_FIXED_HUMAN_RECONCILIATION_ONLY','generation_requests':0,'marker_changes':0}));return 0
    if not sys.stdin.isatty() or os.getuid()==0:raise Blocked('NORMAL_NONROOT_HOST_TTY_REQUIRED')
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':raise Blocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    bindings=load_bindings(repo);operator_raw,_=read_bound(runtime_for(repo)/bindings['operator_name'],bindings['operator_sha256'])
    # Guard is called before any socket/Docker read. Source hashes checked first.
    for rel,digest in bindings['code_files'].items():read_bound(repo/rel,digest,private=False)
    coordinator=ExistingReadOnlyCoordinator(repo,json.loads(operator_raw));coordinator.guard()
    result=(diagnose(repo,bindings,coordinator) if a.diagnose_human_readonly
        else reconcile(repo,bindings,coordinator,DockerReadOnly(coordinator.guard)))
    print(json.dumps(result));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_GENERATION_NO_AUTOMATIC_RETRY','reason':type(exc).__name__+':'+str(exc),
                          'instruction':'Inspect saved audit and original UNKNOWN; do not retry a model request.'}),file=sys.stderr)
        raise SystemExit(1)
