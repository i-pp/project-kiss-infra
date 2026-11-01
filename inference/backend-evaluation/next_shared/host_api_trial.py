"""Human-host-only, one fixed backend/Next ACK trial; no daemon or generic executor."""
import argparse
from contextlib import contextmanager
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
import uuid

from sglang_swap_budget import SGLangBudget,BudgetBlocked,MAX_GROWTH
from paging_telemetry import PagingTelemetry
from owned_memory_telemetry import OwnedMemoryTelemetry
from container_log_capture import capture as capture_container_logs

from fixed_trial_assets import (Blocked,GIB,NETWORK,helpers,model_metadata_unchanged,
                               install_sigterm_handler,operator_record,private_read,safe_path,verify_weights)

ACK='ACEIS_NEXT_BACKEND_ACK'
PORT=30000
WHOLE=900
LABEL='org.aceis.next-trial.'
MODEL_ALIAS='aceis-next-int4-trial'
DOCKER='/usr/bin/docker'
STARTUP_SECONDS={'vllm':90,'sglang':300}
SG_SWAP_OPERATOR_SHA='1415a4dd161956390ec6a71fdbd0e11ffff623cf010b3a0de7a6e3b21d3f2545'
SG_SWAP_APPROVAL='Sentinel_3b6193357af08191b3a0abab95aa38e4'
AITER_RETRY_OPERATOR_SHA='f21b5e7064c7e177052f93e58784d9862a2c251919cc0f4ba5f899bd861cc4ae'
AITER_RETRY_APPROVAL='Sentinel_c374855f7b308191a87d9a41e921de2e'
SEQUENTIAL_OPERATOR_SHA='9f3d6953c389d9bca94020de8b8cdbcaedd4580d458cd78dda57af8073338d96'
SEQUENTIAL_APPROVAL='Sentinel_eebe661ab2088191ae5612d23ecf4d9f'
AITER_PROFILE='existing-512MiB-aiter-subdirectory-v1'
AITER_RECEIPT_SHA='7d465b04cda288dff7f17557d6d2ff350f7fdbf0ab755f0f3259cbb78943c797'
AITER_RECEIPT_RELATIVE='agents/local_llm/.runtime/backend-runtime/aiter-source-inspection/run-2050a4ec1c2c44a693eb0f333826f1cf/receipt.json'


def aiter_retry_profile(record):
    return (record or {}).get('review',{}).get('aiter_cache_profile')==AITER_PROFILE


def validate_aiter_retry(record,backend,digest):
    requested=any(k.startswith('aiter_') for k in record.get('review',{}))
    if not requested and digest not in (AITER_RETRY_OPERATOR_SHA,SEQUENTIAL_OPERATOR_SHA):return None
    review=record.get('review',{})
    if (backend!='sglang' or digest not in (AITER_RETRY_OPERATOR_SHA,SEQUENTIAL_OPERATOR_SHA) or not aiter_retry_profile(record)
        or review.get('aiter_cache_retry_authorization')!=AITER_RETRY_APPROVAL
        or review.get('aiter_cache_retry_max_attempts')!=1
        or review.get('aiter_source_receipt_sha256')!=AITER_RECEIPT_SHA):
        raise Blocked('FIXED_ONE_AITER_RETRY_PROFILE_REQUIRED')
    sequential=review.get('sglang_sequential_loader_profile') is not None
    if sequential or digest==SEQUENTIAL_OPERATOR_SHA:
        if (digest!=SEQUENTIAL_OPERATOR_SHA or review.get('sglang_sequential_loader_profile')!='one-thread-v1'
            or review.get('sglang_sequential_loader_authorization')!=SEQUENTIAL_APPROVAL
            or review.get('sglang_sequential_loader_max_attempts')!=1):
            raise Blocked('FIXED_ONE_SEQUENTIAL_LOADER_RETRY_REQUIRED')
    path=Path(record['project_root'])/AITER_RECEIPT_RELATIVE
    receipt=private_read(path,AITER_RECEIPT_SHA)
    if (receipt.get('status')!='STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS'
        or receipt.get('cpu_container_absence_confirmed') is not True
        or receipt.get('generation_requests')!=0 or receipt.get('gpu_device_access') is not False
        or receipt.get('image')!=record['runtimes']['sglang']['image_ref']):
        raise Blocked('AITER_FIXED_IMAGE_STATIC_EVIDENCE_REQUIRED')
    return {'operator_sha256':digest,'authorization':SEQUENTIAL_APPROVAL if digest==SEQUENTIAL_OPERATOR_SHA else AITER_RETRY_APPROVAL,
            'source_receipt_sha256':AITER_RECEIPT_SHA,'cache':'/jit-cache/aiter',
            'shared_exec_tmpfs_bytes':512<<20,'capacity_sufficiency':'UNMEASURED_NO_AUTOMATIC_EXPANSION'}


def loader_static_preflight(record):
    # Fixed sibling CPU inspector, not an operator-provided executable or module path.
    folder=Path(record['project_root'])/'inference/backend-evaluation/sglang_content_handoff'
    safe_path(folder);sys.path.insert(0,str(folder))
    from inspect_loader_source_host import capture_once
    from loader_static_gate import confirm
    receipt_path=capture_once();raw=receipt_path.read_bytes()
    if len(raw)>65536:raise Blocked('LOADER_STATIC_RECEIPT_LIMIT')
    digest=hashlib.sha256(raw).hexdigest();receipt=private_read(receipt_path,digest)
    if (receipt.get('status')!='STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS'
        or receipt.get('cpu_container_absence_confirmed') is not True
        or receipt.get('image')!=record['runtimes']['sglang']['image_ref']
        or receipt.get('identity',{}).get('image_id')!=record['runtimes']['sglang'].get('image_id')
        or receipt.get('generation_requests')!=0 or receipt.get('gpu_device_access') is not False):
        raise Blocked('LOADER_STATIC_INSPECTION_NOT_CONFIRMED')
    return {'receipt':str(receipt_path),'receipt_sha256':digest,**confirm(receipt['result'])}


class Unknown(RuntimeError):pass


def server_argv(backend,record=None):
    if backend=='vllm':
        return ['vllm','serve','/models/next-int4','--served-model-name',MODEL_ALIAS,
                '--host','0.0.0.0','--port','30000','--load-format','safetensors',
                '--safetensors-load-strategy','lazy','--dtype','bfloat16','--tensor-parallel-size','1',
                '--moe-backend','triton','--attention-backend','TRITON_ATTN',
                '--gdn-prefill-backend','triton','--enforce-eager','--max-model-len','4096',
                '--max-num-seqs','1','--max-num-batched-tokens','512','--gpu-memory-utilization','0.80']
    if backend=='sglang':
        argv=['python3','-m','sglang.launch_server','--model-path','/models/next-int4',
                '--model-impl','sglang','--load-format','safetensors','--served-model-name',MODEL_ALIAS,
                '--host','0.0.0.0','--port','30000','--tp-size','1','--dtype','bfloat16',
                '--context-length','4096','--max-running-requests','1','--max-total-tokens','4096',
                '--chunked-prefill-size','512','--mem-fraction-static','0.80',
                '--attention-backend','triton','--moe-runner-backend','triton',
                '--cuda-graph-backend-decode','disabled','--cuda-graph-backend-prefill','disabled',
                '--skip-server-warmup']
        if (record or {}).get('review',{}).get('sglang_sequential_loader_profile')=='one-thread-v1':
            argv+=['--model-loader-extra-config','{"enable_multithread_load":false,"num_threads":1}']
        mamba_profile=(record or {}).get('review',{}).get('sglang_mamba_cache_profile')
        if mamba_profile is not None:
            if mamba_profile!='cache8-v1':raise Blocked('FIXED_MAMBA8_PROFILE_REQUIRED')
            argv+=['--max-mamba-cache-size','8']
        return argv
    raise Blocked('FIXED_BACKEND_REQUIRED')


def server_environment(backend,record=None):
    base={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1',
          'HOME':'/tmp/aceis-home','TMPDIR':'/tmp','XDG_CACHE_HOME':'/tmp/aceis-cache','TRITON_CACHE_DIR':'/jit-cache/triton',
          'PYTHONDONTWRITEBYTECODE':'1'}
    if backend=='vllm':
        base.update(VLLM_ROCM_USE_AITER='0',VLLM_GDN_DECODE_KERNEL='triton',
                    VLLM_NO_USAGE_STATS='1',VLLM_DO_NOT_TRACK='1',VLLM_PLUGINS='')
    elif backend=='sglang':
        # Fixed image inherits /root/.cargo/bin; UID1000 cannot traverse /root.
        base['PATH']='/opt/venv/bin:/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        base['SGLANG_USE_AITER']='0'
        base['SGLANG_JIT_CACHE_DIR']='/jit-cache/sglang'
        base['TORCHINDUCTOR_CACHE_DIR']='/jit-cache/inductor'
        if aiter_retry_profile(record):base['AITER_JIT_DIR']='/jit-cache/aiter'
    else:raise Blocked('FIXED_BACKEND_REQUIRED')
    return base


class Docker:
    """Fixed local Docker CLI only, guarded before every call. Never used in tests."""
    def __init__(self,guard):self.guard=guard;self.clients_reaped=True;self.deadline=None;self.monitor=None
    def command(self,args,timeout=5,include_stderr=False):
        self.guard()
        if self.monitor is not None:self.monitor()
        if self.deadline is not None:
            left=self.deadline-time.monotonic()
            if left<=0:raise Blocked('DOCKER_STAGE_DEADLINE')
            timeout=min(timeout,left)
        # No inherited Docker context, auth helpers, proxy or injection variables.
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
        try:
            proc=subprocess.Popen([DOCKER,'--host','unix:///var/run/docker.sock',*args],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        except BaseException as exc:
            self.clients_reaped=False
            raise Unknown('DOCKER_SPAWN_OUTCOME_UNKNOWN_NO_HANDLE') from exc
        end=time.monotonic()+max(.1,timeout)
        try:
            while True:
                if self.monitor is not None:self.monitor()
                left=end-time.monotonic()
                if left<=0:raise TimeoutError('DOCKER_RPC_DEADLINE')
                try:
                    stdout,stderr=proc.communicate(timeout=min(.2,left));break
                except subprocess.TimeoutExpired:continue
        except BaseException as exc:
            try:proc.kill()
            except ProcessLookupError:pass
            try:proc.wait(timeout=5)
            except BaseException:self.clients_reaped=False
            raise Unknown('DOCKER_RPC_OUTCOME_UNKNOWN_CLIENT_REAP_'+str(self.clients_reaped)) from exc
        finally:
            for stream in (proc.stdout,proc.stderr):
                if stream is not None:stream.close()
        if len(stdout)>2<<20 or len(stderr)>2<<20:raise Unknown('DOCKER_RESPONSE_LIMIT')
        if proc.returncode:raise Blocked('DOCKER_COMMAND_FAILED:'+str(proc.returncode))
        return (stdout+stderr).decode('utf-8',errors='replace') if include_stderr else stdout.decode('utf-8')
    def image(self,ref):return json.loads(self.command(['image','inspect',ref]))[0]
    def gpu_metadata(self):
        self.guard();rows=[]
        for name in ['/dev/kfd','/dev/dri/renderD128']:
            try:info=os.stat(name)
            except OSError as exc:raise Blocked('FIXED_GPU_DEVICE_UNAVAILABLE') from exc
            if not stat.S_ISCHR(info.st_mode) or not os.access(name,os.R_OK|os.W_OK):
                raise Blocked('EXISTING_SESSION_GPU_DEVICE_ACCESS_REQUIRED')
            rows.append({'path':name,'uid':info.st_uid,'gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode)})
        return rows  # metadata only: no device open/ioctl or group changes
    def network(self):return json.loads(self.command(['network','inspect',NETWORK]))[0]
    def find(self,name):
        ids=self.command(['container','ls','-a','--no-trunc','--filter','name=^/'+name+'$','--format','{{.ID}}']).splitlines()
        if not ids:return None
        if len(ids)!=1 or not re.fullmatch('[0-9a-f]{64}',ids[0]):raise Unknown('CONTAINER_DISCOVERY_AMBIGUOUS')
        return json.loads(self.command(['container','inspect',ids[0]]))[0]
    def create(self,identity,record,backend):
        argv=server_argv(backend,record)
        args=['container','create','--pull=never','--name',identity['name'],
              '--label',LABEL+'token='+identity['token'],'--label',LABEL+'owner='+identity['owner'],
              '--label',LABEL+'backend='+backend,'--memory','32g','--memory-swap','32g',
              '--read-only','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=2g',
              '--tmpfs','/jit-cache:rw,exec,nosuid,nodev,size=512m,mode=0700,uid='+str(os.getuid())+',gid='+str(os.getgid()),
              '--pids-limit','512','--cpus','8','--shm-size','2g','--ipc','private',
              '--no-healthcheck','--network',NETWORK,
              '--user',str(os.getuid())+':'+str(os.getgid()),'--device','/dev/kfd:/dev/kfd',
              '--device','/dev/dri/renderD128:/dev/dri/renderD128','--cap-drop','ALL',
              '--security-opt','no-new-privileges:true','--init','--restart','no',
              '--mount','type=bind,source='+record['model_dir']+',target=/models/next-int4,readonly',
              '--entrypoint',argv[0]]
        # Preserve only GPU-device groups already held by this human session.
        for group in sorted({os.stat(p).st_gid for p in ['/dev/kfd','/dev/dri/renderD128']} & set(os.getgroups())):
            args+=['--group-add',str(group)]
        for key,value in server_environment(backend,record).items():args+=['--env',key+'='+value]
        args+=[record['runtimes'][backend]['image_ref'],*argv[1:]]
        return self.command(args,timeout=15).strip()
    def start(self,cid):return self.command(['container','start',cid],timeout=15)
    def stop(self,cid,timeout=15):return self.command(['container','stop','--time','10',cid],timeout=timeout)
    def kill(self,cid,timeout=5):return self.command(['container','kill',cid],timeout=timeout)
    def remove(self,cid,timeout=5):return self.command(['container','rm',cid],timeout=timeout)
    def logs(self,cid,timeout=3):
        return capture_container_logs(self,cid,timeout)


def match_owned(row,identity,backend,record,allow_new_cid=False):
    if row is None:raise Unknown('OWNED_CONTAINER_NOT_OBSERVED')
    cid=row.get('Id','')
    labels=row.get('Config',{}).get('Labels') or {}
    if (not re.fullmatch('[0-9a-f]{64}',cid) or row.get('Name')!='/'+identity['name']
        or row.get('Image')!=record['runtimes'][backend]['image_id']
        or labels.get(LABEL+'token')!=identity['token']
        or labels.get(LABEL+'owner')!=identity['owner']
        or labels.get(LABEL+'backend')!=backend
        or (identity.get('cid') is not None and cid!=identity['cid'])):
        raise Unknown('CONTAINER_IDENTITY_MISMATCH_NO_SIGNAL')
    if identity.get('cid') is None and not allow_new_cid:raise Unknown('CID_NOT_ESTABLISHED')
    return cid


def verify_container_contract(row,record,backend):
    host=row.get('HostConfig',{});config=row.get('Config',{})
    if (host.get('Memory')!=32*GIB or host.get('MemorySwap')!=32*GIB
        or host.get('ReadonlyRootfs') is not True
        or host.get('Tmpfs')!={'/tmp':'rw,noexec,nosuid,nodev,size=2g',
                                  '/jit-cache':'rw,exec,nosuid,nodev,size=512m,mode=0700,uid='+str(os.getuid())+',gid='+str(os.getgid())}
        or host.get('Privileged') or host.get('NetworkMode')!=NETWORK
        or host.get('PidsLimit')!=512 or host.get('NanoCpus')!=8_000_000_000 or host.get('Init') is not True
        or host.get('IpcMode') not in ('private','')
        or host.get('CapDrop')!=['ALL']
        or host.get('SecurityOpt') not in (['no-new-privileges:true'],['no-new-privileges'])
        or host.get('CapAdd') not in (None,[]) or host.get('PidMode') not in ('',None)
        or host.get('UTSMode') not in ('',None) or host.get('CgroupnsMode') not in ('private','',None)
        or host.get('PortBindings') not in (None,{}) or host.get('PublishAllPorts')):
        raise Blocked('CONTAINER_MEMORY_OR_SECURITY_CONTRACT_MISMATCH')
    mounts=[m for m in row.get('Mounts',[]) if not (m.get('Type')=='tmpfs' and m.get('Destination') in {'/tmp','/jit-cache'})]
    if len(mounts)!=1 or mounts[0].get('Source')!=record['model_dir'] or mounts[0].get('Destination')!='/models/next-int4' or mounts[0].get('RW') is not False:
        raise Blocked('FIXED_READONLY_MODEL_MOUNT_REQUIRED')
    if backend=='sglang' and aiter_retry_profile(record):
        # Fixed startup environment, established before Python/AITER imports.
        expected=server_environment(backend,record)
        env=config.get('Env') or []
        for key,value in expected.items():
            entries=[e for e in env if e.startswith(key+'=')]
            if entries!=[key+'='+value]:raise Blocked('FIXED_AITER_STARTUP_ENVIRONMENT_MISMATCH')
    argv=server_argv(backend,record)
    if (config.get('Entrypoint')!=[argv[0]] or config.get('Cmd')!=argv[1:]
        or config.get('User')!=str(os.getuid())+':'+str(os.getgid()) or os.getuid()==0
        or config.get('Healthcheck',{}).get('Test')!=['NONE']):
        raise Blocked('FIXED_SERVER_ARGV_OR_NONROOT_USER_MISMATCH')


def read_network_profile(record):
    path=safe_path(Path(record['project_root'])/'agents/local_llm/.runtime/router-host-profile.json')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        s=os.fstat(f.fileno())
        if s.st_uid!=os.getuid() or (s.st_mode & 0o777)!=0o600:raise Blocked('PRIVATE_ROUTER_PROFILE_REQUIRED')
        raw=f.read(65537)
    if len(raw)>65536:raise Blocked('ROUTER_PROFILE_LIMIT')
    d=json.loads(raw)
    if d.get('existing_internal_network')!=NETWORK or not re.fullmatch('[0-9a-f]{64}',d.get('internal_network_id','')):
        raise Blocked('REVIEWED_ROUTER_NETWORK_ID_REQUIRED')
    return {'name':NETWORK,'id':d['internal_network_id']}


def validate_network(network,profile):
    if (network.get('Name')!=NETWORK or profile.get('name')!=NETWORK or network.get('Id')!=profile.get('id')
        or network.get('Internal') is not True or network.get('Driver')!='bridge' or network.get('Scope')!='local'):
        raise Blocked('EXISTING_INTERNAL_NETWORK_ID_MISMATCH')
    subnets=[ipaddress.IPv4Network(x['Subnet'],strict=True) for x in network.get('IPAM',{}).get('Config',[]) if ':' not in x.get('Subnet','')]
    private=[ipaddress.IPv4Network(x) for x in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']]
    if len(subnets)!=1 or not any(subnets[0].subnet_of(x) for x in private):raise Blocked('FIXED_PRIVATE_SUBNET_REQUIRED')
    return subnets[0]


def capture_route(row,network,profile):
    subnet=validate_network(network,profile)
    endpoints=row.get('NetworkSettings',{}).get('Networks',{})
    if set(endpoints)!={NETWORK}:raise Unknown('EXTRA_OR_MISSING_CONTAINER_NETWORK')
    ep=endpoints[NETWORK];peer=(network.get('Containers') or {}).get(row['Id'],{})
    ip=ipaddress.IPv4Address(ep.get('IPAddress',''))
    if (ep.get('NetworkID')!=network['Id'] or not re.fullmatch('[0-9a-f]{64}',ep.get('EndpointID',''))
        or ip not in subnet or ip in (subnet.network_address,subnet.broadcast_address)
        or ep.get('IPPrefixLen')!=subnet.prefixlen or peer.get('EndpointID')!=ep['EndpointID']
        or peer.get('Name')!=row['Name'].lstrip('/') or peer.get('IPv4Address')!=str(ip)+'/'+str(subnet.prefixlen)):
        raise Unknown('OWNED_INTERNAL_ENDPOINT_MISMATCH')
    return {'network_name':NETWORK,'network_id':network['Id'],'container_id':row['Id'],
            'endpoint_id':ep['EndpointID'],'ipv4':str(ip),'subnet':str(subnet),'port':30000}


class LocalHTTP:
    def __init__(self):
        self.route=None;self.confirm=None;self.connection=None;self.active_socket=None;self.deadline=None
        self.aborted=threading.Event();self.connection_lock=threading.Lock();self.post_intended=False
    def arm(self):
        with self.connection_lock:
            if self.connection is not None:raise Unknown('PREVIOUS_HTTP_NOT_FINISHED')
            self.aborted.clear()
    def abort(self):
        self.aborted.set()
        with self.connection_lock:connection=self.connection;active_socket=self.active_socket
        sock=active_socket or (None if connection is None else connection.sock)
        if sock is not None:
            try:sock.shutdown(2)
            except OSError:pass
            sock.close()
        if connection is not None:
            connection.close()
    def bind_route(self,route,confirm):
        if self.route is not None:raise Blocked('TRIAL_ROUTE_ALREADY_FIXED')
        self.route=dict(route);self.confirm=confirm
    def request(self,method,path,body=None,timeout=2):
        if (method,path) not in {('GET','/v1/models'),('POST','/v1/chat/completions')}:
            raise Blocked('FIXED_INTERNAL_HTTP_OPERATION_REQUIRED')
        if self.route is None or self.confirm is None:raise Blocked('OWNED_ROUTE_NOT_CONFIRMED')
        if self.confirm()!=self.route:raise Unknown('OWNED_ENDPOINT_CHANGED_NO_RETRY')
        if self.deadline is not None:
            timeout=min(timeout,self.deadline-time.monotonic())
            if timeout<=0:
                if method=='GET':raise Blocked('READINESS_DEADLINE_BEFORE_SEND')
                raise Unknown('HTTP_STAGE_DEADLINE_BEFORE_SEND')
        if self.aborted.is_set():
            if method=='GET':raise Blocked('READINESS_ABORTED_BEFORE_SEND')
            raise Unknown('HTTP_ABORTED_BEFORE_SEND')
        if method=='POST':
            if self.post_intended:raise Blocked('POST_ALREADY_INTENDED_NO_RETRY')
            self.post_intended=True
        data=None if body is None else json.dumps(body).encode()
        connection=http.client.HTTPConnection(self.route['ipv4'],30000,timeout=min(2,timeout))
        # An abort between the checks and request must never auto-reconnect/send.
        connection.auto_open=0
        with self.connection_lock:self.connection=connection
        try:
            connection.connect()
            with self.connection_lock:self.active_socket=connection.sock
            if self.aborted.is_set():
                if method=='GET':raise Blocked('READINESS_ABORTED_BEFORE_SEND')
                raise Unknown('HTTP_ABORTED_BEFORE_SEND')
            if self.deadline is not None:
                timeout=min(timeout,self.deadline-time.monotonic())
                if timeout<=0:
                    if method=='GET':raise Blocked('READINESS_DEADLINE_AFTER_CONNECT')
                    raise Unknown('HTTP_STAGE_DEADLINE_AFTER_CONNECT')
            connection.sock.settimeout(timeout)
            connection.request(method,path,body=data,headers={'Content-Type':'application/json'})
            r=connection.getresponse()
            if r.status!=200:raise Blocked('API_NON_200_NO_REDIRECT')
            raw=r.read((1<<20)+1)
        finally:
            connection.close()
            with self.connection_lock:self.connection=None;self.active_socket=None
        if len(raw)>1<<20:raise Unknown('API_RESPONSE_LIMIT')
        return json.loads(raw)


class Trial:
    def __init__(self,record,backend,coordinator,driver,http,probe,run,write,policy,
                 verify=verify_weights,unchanged=model_metadata_unchanged,
                 clock=time.monotonic,sleep=time.sleep,network_profile=None,start_time=None,reserve_attempt=None,operator_sha256=None):
        self.r=record;self.backend=backend;self.c=coordinator;self.driver=driver;self.http=http
        self.probe=probe;self.run=Path(run);self.write=write;self.policy=policy
        self.verify=verify;self.unchanged=unchanged;self.clock=clock;self.sleep=sleep;self.network_profile=network_profile
        self.route_receipt=None
        self.reserve_attempt=reserve_attempt
        self.operator_sha256=operator_sha256
        self.sg_swap_enabled=backend=='sglang' and operator_sha256 in (SG_SWAP_OPERATOR_SHA,AITER_RETRY_OPERATOR_SHA,SEQUENTIAL_OPERATOR_SHA)
        self.sg_swap_budget=None;self.resource_failure=None
        self.owned_memory=OwnedMemoryTelemetry() if operator_sha256==SEQUENTIAL_OPERATOR_SHA else None
        self.paging=PagingTelemetry() if self.sg_swap_enabled else None
        self.start_time=clock() if start_time is None else start_time
        self.before=None;self.post_intents=0;self.generation_confirmed=False;self.loading_pressure=[]
        self.resource_samples=0;self.resource_extrema={};self.resource_lock=threading.Lock()
        token=uuid.uuid4().hex
        self.identity={'name':'aceis-next-'+backend+'-'+token[:12],'token':token,'owner':str(os.getuid()),'cid':None}
        self.create_intent=False;self.create_unknown=False;self.cleanup_safe=True

    def log(self,event,**values):
        row={'event':event,'elapsed':round(self.clock()-self.start_time,3),**values}
        # Exclusive numbered files avoid journal truncation/overwrite on a failed process.
        path=self.run/('event-'+uuid.uuid4().hex+'.json');self.write(path,row)
        print(json.dumps(row),flush=True)

    def remaining(self,limit):
        left=WHOLE-(self.clock()-self.start_time)-185
        if left<=0:raise Blocked('WHOLE_DEADLINE_RECOVERY_RESERVED')
        return min(limit,left)

    def safety(self,start=False):
        if self.loading_pressure:raise Blocked('STARTUP_RESOURCE_MONITOR_ABORT')
        probe_error=None
        try:observed=self.probe()
        except Exception as exc:
            if not self.sg_swap_enabled:raise
            observed=None;probe_error=type(exc).__name__
        failure=None;log_failure=False
        with self.resource_lock:
            if self.sg_swap_enabled:
                # One reviewed immutable operator only. First failure is sticky;
                # later normal readings cannot resume or rebaseline this trial.
                if self.resource_failure is not None:failure=self.resource_failure
                else:
                    self.paging.sample(self.clock())
                    try:
                        if probe_error is not None:raise BudgetBlocked('RESOURCE_PROBE_FAILED')
                        if self.sg_swap_budget is None:self.sg_swap_budget=SGLangBudget(self.before)
                        self.sg_swap_budget.observe(observed,start=start)
                    except BudgetBlocked as exc:
                        failure={'reason':str(exc),'observed':dict(observed) if isinstance(observed,dict) else observed,
                            'baseline':dict(self.before) if isinstance(self.before,dict) else None,
                            'probe_error_class':probe_error,'swap_growth_limit_bytes':MAX_GROWTH,
                            'approval':SG_SWAP_APPROVAL,'details':getattr(exc,'resource_evidence',None)}
                        self.resource_failure=failure;log_failure=True
            if isinstance(observed,dict):
                self.resource_samples+=1
                for name,value in observed.items():
                    if name not in {'mem_available','gpu_used','swap_used'} or value is None:continue
                    previous=self.resource_extrema.get(name,value)
                    if type(value) is int:
                        self.resource_extrema[name]=min(previous,value) if name=='mem_available' else max(previous,value)
        if failure is not None:
            if log_failure:self.log('resource_threshold_exceeded',**failure)
            exc=Blocked('RESOURCE_THRESHOLD_EXCEEDED:'+failure['reason']);exc.resource_evidence=failure;raise exc
        if not self.sg_swap_enabled:
            low_ram=observed['mem_available']<24*GIB if start else observed['mem_available']<=16*GIB
            if (low_ram or observed['gpu_used'] is None or observed['gpu_used']>58*GIB
                    or observed['swap_used']>self.before['swap_used']):raise Blocked('RESOURCE_THRESHOLD_EXCEEDED')
        return observed

    def monitor_rpc(self):
        self.safety();self.remaining(1)

    @contextmanager
    def loading_monitor(self,end):
        stop=threading.Event()
        def observe():
            while not stop.wait(.2):
                try:
                    self.monitor_rpc()
                    if self.clock()>=end:raise Blocked('STARTUP_'+str(STARTUP_SECONDS[self.backend])+'_SECONDS_EXCEEDED')
                except BaseException:
                    self.loading_pressure.append('RESOURCE_OR_DEADLINE')
                    self.http.abort();return
        watcher=threading.Thread(target=observe,daemon=True);watcher.start()
        try:
            yield
            if self.loading_pressure:raise Blocked('STARTUP_RESOURCE_MONITOR_ABORT')
        finally:stop.set();watcher.join(timeout=2)

    def observed(self,allow_new=False):
        row=self.driver.find(self.identity['name'])
        cid=match_owned(row,self.identity,self.backend,self.r,allow_new_cid=allow_new)
        self.identity['cid']=cid
        if self.owned_memory is not None and row.get('State',{}).get('Running') is True:
            self.owned_memory.observe(cid,row['State'].get('Pid'),self.clock())
        return row

    def confirm_route(self):
        route=capture_route(self.observed(),self.driver.network(),self.network_profile)
        if self.route_receipt is not None and route!=self.route_receipt:raise Unknown('OWNED_ENDPOINT_CHANGED_NO_RETRY')
        return route

    def cleanup(self):
        """Stop/kill only a positively owned immutable CID, then remove/verify absence."""
        self.driver.monitor=None  # pressure must not prevent resource release
        if not self.create_intent:return True
        end=self.clock()+45
        self.driver.deadline=end
        try:
            row=self.driver.find(self.identity['name'])
            if row is None:
                # A timed-out create can arrive later: current absence is insufficient.
                return not self.create_unknown and self.identity['cid'] is None
            cid=match_owned(row,self.identity,self.backend,self.r,allow_new_cid=True)
            self.identity['cid']=cid
            if row.get('State',{}).get('Running'):
                try:self.driver.stop(cid,timeout=min(15,max(.1,end-self.clock())))
                except (Unknown,Blocked):pass
                row=self.observed()
                if row.get('State',{}).get('Running'):
                    try:self.driver.kill(cid,timeout=min(5,max(.1,end-self.clock())))
                    except (Unknown,Blocked):pass
            while True:
                row=self.observed()
                state=row.get('State',{})
                if state.get('Running') is False and state.get('Pid')==0 and state.get('Status') in {'created','exited','dead'}:break
                if self.clock()>=end:return False
                self.sleep(.2)
            # Terminal inspect is required before remove; no --force and no broad pruning.
            self.log('owned_container_terminal',cid=cid,state=state.get('Status'),
                     exit_code=state.get('ExitCode') if type(state.get('ExitCode')) is int else None,
                     oom_killed=state.get('OOMKilled') if type(state.get('OOMKilled')) is bool else None,
                     finished_at=state.get('FinishedAt')[:64] if type(state.get('FinishedAt')) is str else None,
                     terminal_state_fields_present={key:key in state for key in ('ExitCode','OOMKilled','FinishedAt')})
            try:
                tail=self.driver.logs(cid,timeout=min(3,max(.1,end-self.clock())))
                capture=tail if isinstance(tail,dict) else {'stdout':tail,'stderr':'',
                    'complete_stream':False,'truncated':True,'incomplete_reason':'LEGACY_DRIVER_CAPTURE'}
                self.write(self.run/'server-log-tail.json',{'container_id':cid,'untrusted_text':True,
                    'terminal_before_read':True,**capture})
            except Exception as exc:self.log('owned_logs_unavailable',reason=type(exc).__name__)
            try:self.driver.remove(cid,timeout=min(5,max(.1,end-self.clock())))
            except (Unknown,Blocked):pass
            if self.driver.find(self.identity['name']) is not None:return False
            # Removal makes an in-flight start for the original CID unable to run later.
            return getattr(self.driver,'clients_reaped',True)
        except BaseException as exc:
            self.log('owned_cleanup_unconfirmed',reason=type(exc).__name__)
            return False

    def startup(self,end):
        self.driver.deadline=end;self.http.deadline=end
        while True:
            if self.clock()>=end:raise Blocked('STARTUP_'+str(STARTUP_SECONDS[self.backend])+'_SECONDS_EXCEEDED')
            self.safety();self.remaining(1)
            row=self.observed()
            if row.get('State',{}).get('Running') is not True:raise Blocked('SERVER_CONTAINER_EXITED')
            try:
                self.http.arm()
                data=self.http.request('GET','/v1/models',timeout=min(2,max(.1,end-self.clock())))
                if self.clock()>=end:raise Blocked('STARTUP_'+str(STARTUP_SECONDS[self.backend])+'_SECONDS_EXCEEDED')
                if [x.get('id') for x in data.get('data',[])]==[MODEL_ALIAS]:return
            except (OSError,ValueError,Blocked):pass  # only bounded read-only readiness repeats
            if self.clock()>=end:raise Blocked('STARTUP_'+str(STARTUP_SECONDS[self.backend])+'_SECONDS_EXCEEDED')
            self.sleep(.2)

    def generate_once(self):
        self.safety();timeout=self.remaining(90)
        end=self.clock()+timeout;self.driver.deadline=end;self.http.deadline=end
        policy=self.policy('draft')
        if not policy.get('system') or not policy.get('metadata'):raise Blocked('COMMON_POLICY_MISSING')
        body={'model':MODEL_ALIAS,'messages':[{'role':'system','content':policy['system']},
               {'role':'user','content':'Reply with exactly '+ACK+' and no other text.'}],
               'temperature':0,'seed':42,'max_tokens':64,'stream':False}
        self.write(self.run/'request.json',{'body':body,'policy':policy['metadata']})
        self.write(self.run/'post-intent.json',{'request_count':1,'automatic_retry':False})
        self.post_intents=1;self.http.arm()
        stop=threading.Event();pressure=[]
        def observe():
            while not stop.wait(.05):
                try:
                    self.safety();self.remaining(1)
                    if self.clock()>=end:raise Blocked('GENERATION_STAGE_DEADLINE')
                except BaseException:
                    pressure.append('RESOURCE_OR_DEADLINE');self.http.abort();return
        watcher=threading.Thread(target=observe,daemon=True);watcher.start()
        request_started=self.clock()
        try:
            # Transport stays in the caller. No worker can submit a late POST after recovery.
            answer=self.http.request('POST','/v1/chat/completions',body,timeout=timeout)
            if pressure or self.clock()>=end:raise Unknown('POST_INTERRUPTED_BY_RESOURCE_OR_DEADLINE')
        except BaseException as exc:
            self.http.abort();raise Unknown('POST_RESULT_UNKNOWN_NO_RETRY:'+type(exc).__name__) from exc
        finally:
            stop.set();watcher.join(timeout=2)
        self.write(self.run/'response.json',answer)
        choices=answer.get('choices',[])
        if len(choices)!=1:raise Unknown('UNEXPECTED_API_RESULT_NO_RETRY')
        c=choices[0];text=c.get('message',{}).get('content');finish=c.get('finish_reason')
        self.generation_confirmed=True
        api_seconds=self.clock()-request_started
        completion=(answer.get('usage') or {}).get('completion_tokens')
        return {'environment':'PASS','quality':'ACK_ONLY_PASS' if text==ACK and finish=='stop' else 'ACK_FORMAT_FAIL',
                'content':text,'finish_reason':finish,'usage':answer.get('usage'),
                'api_call_seconds_including_route_checks':api_seconds,
                'completion_tokens_per_api_second':completion/api_seconds if isinstance(completion,int) and api_seconds>0 else None,
                'speed_is_not_decode_benchmark':True,
                'policy':policy['metadata'],'model_quality_general':'NOT_ESTIMATED',
                'code_executed':False,'untrusted_advisory':True}

    def execute(self):
        out={'status':'FAILED','backend':self.backend,'environment':'NOT_RUN','quality':'UNASSESSED',
             'generation_requests':0,'restoration':'NOT_NEEDED','automatic_retry':False,'code_executed':False}
        fingerprints=[]
        try:
            self.c.guard()
            with self.c.locked():
                self.c.guard();self.c.idle()
                self.log('policy_preflight_start')
                try:
                    policy=self.policy('draft')
                    if not policy.get('system') or not policy.get('metadata'):raise Blocked('COMMON_POLICY_MISSING')
                    self.write(self.run/'policy-preflight.json',{'status':'VERIFIED','metadata':policy['metadata'],
                               'post_policy_revalidation_required':True})
                except Exception as exc:
                    self.write(self.run/'policy-preflight-failure.json',{'error_class':type(exc).__name__,
                               'code':getattr(exc,'code',None),'diagnostics':getattr(exc,'diagnostics',None),
                               'generation_requests':0,'model_lifecycle_requests':0})
                    raise
                self.log('policy_preflight_verified')
                self.before=self.probe();self.safety(start=True)
                self.driver.monitor=self.monitor_rpc
                self.driver.deadline=self.start_time+WHOLE-185
                try:
                    self.write(self.run/'resource-policy.json',{'approval':SG_SWAP_APPROVAL if self.sg_swap_enabled else None,
                        'continuation_authorization':SEQUENTIAL_APPROVAL if self.operator_sha256==SEQUENTIAL_OPERATOR_SHA else AITER_RETRY_APPROVAL if self.operator_sha256==AITER_RETRY_OPERATOR_SHA else None,
                        'operator_scope_sha256':self.operator_sha256 if self.sg_swap_enabled else None,
                        'baseline':dict(self.before),'swap_growth_limit_bytes':MAX_GROWTH if self.sg_swap_enabled else 0,
                        'baseline_reset_after_assets':False})
                    self.log('verify_assets_start')
                    def check_assets():self.safety(start=True);self.remaining(1)
                    fingerprints=self.verify(self.r['model_dir'],check=check_assets);self.remaining(1)
                    self.network_profile=self.network_profile or read_network_profile(self.r)
                    validate_network(self.driver.network(),self.network_profile)
                    image=self.driver.image(self.r['runtimes'][self.backend]['image_ref'])
                    if image.get('Id')!=self.r['runtimes'][self.backend]['image_id']:raise Blocked('REVIEWED_IMAGE_ID_MISMATCH')
                    if image.get('Config',{}).get('Volumes'):raise Blocked('IMAGE_AUTOMATIC_VOLUMES_PROHIBITED')
                    self.write(self.run/'gpu-device-metadata.json',self.driver.gpu_metadata())
                    if self.driver.find(self.identity['name']) is not None:raise Blocked('NAME_ALREADY_EXISTS')
                    self.safety(start=True)
                    self.write(self.run/'identity.json',self.identity)
                    if self.remaining(30)<30:raise Blocked('UNLOAD30_SECONDS_PLUS_RECOVERY_NOT_AVAILABLE')
                    if self.reserve_attempt is not None:self.reserve_attempt()
                    self.log('unload30b_intent');self.c.unload();self.log('unload30b_confirmed')
                    self.create_intent=True;self.cleanup_safe=False
                    self.log('create_owned_intent',name=self.identity['name'])
                    try:cid=self.driver.create(self.identity,self.r,self.backend)
                    except BaseException:self.create_unknown=True;raise
                    if not re.fullmatch('[0-9a-f]{64}',cid):self.create_unknown=True;raise Unknown('CREATE_RESULT_UNKNOWN')
                    self.identity['cid']=cid
                    row=self.observed();verify_container_contract(row,self.r,self.backend)
                    self.safety(start=True);self.remaining(STARTUP_SECONDS[self.backend])
                    start_deadline=self.clock()+self.remaining(STARTUP_SECONDS[self.backend]);self.driver.deadline=start_deadline
                    self.log('start_owned_intent',cid=cid,startup_budget_seconds=STARTUP_SECONDS[self.backend],whole_budget_seconds=WHOLE)
                    with self.loading_monitor(start_deadline):
                        try:self.driver.start(cid)
                        except BaseException as exc:raise Unknown('START_RESULT_UNKNOWN_NO_RETRY') from exc
                        out['environment']='FAIL'
                        self.route_receipt=self.confirm_route();self.write(self.run/'temporary-route.json',self.route_receipt)
                        self.http.bind_route(self.route_receipt,self.confirm_route)
                        self.startup(start_deadline)
                    out.update(self.generate_once());out['status']='COMPLETED'
                except BaseException as exc:
                    out['reason']=type(exc).__name__+':'+str(exc)[:180]
                    if isinstance(exc,Unknown) or (self.post_intents and not self.generation_confirmed):
                        out['status']='UNKNOWN';out['generation_uncertain']=bool(self.post_intents)
                    self.log('trial_failed',reason=out['reason'])
                finally:
                    self.cleanup_safe=self.cleanup()
                    out['cleanup_confirmed']=self.cleanup_safe
                    if self.c.mutated:
                        if self.cleanup_safe:
                            try:out['restoration']=self.c.restore()
                            except BaseException:
                                self.c.uncertain('NEXT_API_TRIAL_RESTORE_UNKNOWN');out.update(status='UNKNOWN',restoration='UNKNOWN')
                        else:
                            self.c.uncertain('NEXT_API_TRIAL_CLEANUP_UNKNOWN');out.update(status='UNKNOWN',restoration='BLOCKED_UNCONFIRMED_CLEANUP')
                    if out['status']=='UNKNOWN':self.c.uncertain('NEXT_API_TRIAL_OUTCOME_UNKNOWN_NO_RETRY')
                    out['source_metadata_unchanged']=self.unchanged(fingerprints) if fingerprints else None
                    if out['source_metadata_unchanged'] is False:
                        if out['status']!='UNKNOWN':out.update(status='FAILED',reason='MODEL_SOURCE_METADATA_CHANGED')
                    try:after=self.probe()
                    except BaseException:
                        after={'status':'UNKNOWN'};out['status']='UNKNOWN';self.c.uncertain('NEXT_API_FINAL_RESOURCE_PROBE_UNKNOWN')
                    out.update(generation_requests=self.post_intents,generation_request_intents=self.post_intents,
                               startup_budget_seconds=STARTUP_SECONDS[self.backend],
                               resources_before=self.before,resources_after=after,elapsed_seconds=self.clock()-self.start_time,
                               resource_samples=self.resource_samples,sampled_resource_extrema=self.resource_extrema,
                               resource_extrema_are_sampled_not_hard_limits=True,
                               swap_growth_policy={'scoped_operator':self.sg_swap_enabled,'max_growth_bytes':MAX_GROWTH if self.sg_swap_enabled else 0,
                                   'baseline':self.sg_swap_budget.baseline if self.sg_swap_budget else self.before,
                                   'peak_growth_bytes':self.sg_swap_budget.peak_growth if self.sg_swap_budget else None,
                                   'first_failure':self.resource_failure},
                               host_paging_telemetry=self.paging.snapshot() if self.paging else None,
                               owned_memory_telemetry=self.owned_memory.snapshot() if self.owned_memory else None)
                    if out['elapsed_seconds']>WHOLE:
                        out['whole_deadline_exceeded']=True
                        if out['status']!='UNKNOWN':out.update(status='FAILED',reason='WHOLE900_SECONDS_EXCEEDED')
        except BaseException as exc:
            out['reason']=type(exc).__name__+':'+str(exc)[:180]
        self.write(self.run/'summary.json',out)
        return out


def approved_attempt_path(root,backend,digest):
    if backend not in ('vllm','sglang') or not re.fullmatch('[0-9a-f]{64}',digest or ''):
        raise Blocked('FIXED_APPROVED_ATTEMPT_ID_REQUIRED')
    return Path(root)/('attempt-'+backend+'-'+digest+'.json')


def reserve_approved_attempt(root,backend,digest,run):
    """One model-start attempt per immutable operator; after read-only preflight."""
    path=approved_attempt_path(root,backend,digest)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump({'backend':backend,'operator_sha256':digest,'run':str(run),
                   'attempt_limit':1,'generation_request_limit':1,'automatic_retry':False},f)
        f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-human-approved',action='store_true');p.add_argument('--backend',choices=['vllm','sglang'])
    p.add_argument('--operator-json',type=Path);p.add_argument('--operator-sha256')
    a=p.parse_args()
    if not a.run_human_approved:
        print(json.dumps({'status':'PREPARED_INDIVIDUAL_APPROVAL_REQUIRED','generation_requests':0,'context':4096}));return 0
    started=time.monotonic()
    if a.backend is None:raise Blocked('FIXED_BACKEND_REQUIRED')
    if not sys.stdin.isatty():raise Blocked('HUMAN_HOST_TERMINAL_REQUIRED')
    install_sigterm_handler()
    record=operator_record(a.operator_json,a.operator_sha256,backend=a.backend)
    aiter_evidence=validate_aiter_retry(record,a.backend,a.operator_sha256)
    Coordinator,private_dir,write,probe=helpers();c=Coordinator(record['project_root'],record)
    c.guard()  # No Docker/resource/GPU action before TTY and normal-host evidence.
    if os.getuid()==0:raise Blocked('NONROOT_HUMAN_SESSION_REQUIRED')
    root=private_dir(Path(record['project_root'])/'agents/local_llm/.runtime/backend-api-trials')
    marker=approved_attempt_path(root,a.backend,a.operator_sha256)
    if marker.exists() or marker.is_symlink():raise Blocked('APPROVED_ATTEMPT_ALREADY_RESERVED_NO_RETRY')
    run=private_dir(root/(a.backend+'-'+uuid.uuid4().hex))
    if aiter_evidence is not None:write(run/'aiter-cache-profile.json',aiter_evidence)
    if a.operator_sha256==SEQUENTIAL_OPERATOR_SHA:
        # Distinct from the generation attempt: one CPU preflight, no blind repeat.
        write(root/('preflight-sglang-'+a.operator_sha256+'.json'),{'run':str(run),'automatic_retry':False})
        print('Checking fixed image loader source as data before any 30B unload.',flush=True)
        write(run/'loader-static-preflight.json',loader_static_preflight(record))
        c.guard()
    sys.path.insert(0,str(Path(record['project_root'])/'agents/local_llm'))
    from local_llm import policy_context
    result=Trial(record,a.backend,c,Docker(c.guard),LocalHTTP(),probe,run,write,policy_context,
        start_time=started,reserve_attempt=lambda:reserve_approved_attempt(root,a.backend,a.operator_sha256,run),
        operator_sha256=a.operator_sha256).execute()
    print(json.dumps(result));return 0 if result['status']=='COMPLETED' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_RETRY','reason':type(exc).__name__+':'+str(exc)[:180]}),file=sys.stderr)
        raise SystemExit(1)
