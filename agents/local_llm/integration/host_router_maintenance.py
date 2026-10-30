"""Human-run, fixed Docker maintenance transaction. Never called by MCP/Codex."""
import datetime
import configparser
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid
import ipaddress

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import endpoint_config

LLM = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15'
ROUTER = 'project-kiss-aceis-router'
PROJECT = 'project-kiss-aceis-router'
ORIGINAL = '/project-kiss-phase2-llama-server-1'
ROUTER_ARGS = ['--models-preset','/config/models.ini','--models-max','1','--no-models-autoload','--host','0.0.0.0','--port','8080','--offline','--no-ui']


class Failure(RuntimeError):
    def __init__(self,code,message,exit_code=1):
        super().__init__(message);self.code=code;self.exit_code=exit_code


def private_json(path):
    s=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_size>16384:
        raise Failure('UNSAFE_METADATA','Private owner metadata required')
    return json.loads(path.read_text())


class Maintenance:
    def __init__(self,llm=LLM,execute=subprocess.run,*,expected_existing_user=None):
        self.llm=Path(llm);self.repo=self.llm.parents[1];self.root=self.llm/'.runtime'
        s=self.root.lstat()
        if self.root.is_symlink() or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
            raise Failure('UNSAFE_RUNTIME','Owner-only runtime required')
        self.execute=execute;self.step='initializing';self.lock_fd=None;self.state=None
        self.started=time.monotonic();self.deployment_started=False;self.recovery_deadline=None
        self.internal_route=False;self.candidate=None
        self.log_since=datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.log_path=self.root/('host-maintenance-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.jsonl')
        self.log=os.fdopen(os.open(self.log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w')
        try:
            self.profile=private_json(self.root/'router-host-profile.json')
            if self.profile.get('project_root')!=str(self.repo) or self.profile.get('image')!=IMAGE or self.profile.get('router_name')!=ROUTER:
                raise Failure('HOST_PROFILE_MISMATCH','Host profile differs from fixed deployment')
            self.original_id=self.profile.get('resident_container_id','')
            if not re.fullmatch('[0-9a-f]{64}',self.original_id):raise Failure('INVALID_ORIGINAL_ID','Saved original CID required')
            self.state_path=self.root/'router-host-state.json'
            if self.state_path.exists():
                self.state=private_json(self.state_path)
                if self.state.get('schema')!=1 or self.state.get('resident_cid')!=self.original_id or not re.fullmatch('[0-9a-f]{32}',self.state.get('token','')):
                    raise Failure('STATE_MISMATCH','Deployment ownership state differs; do not overwrite')
            current_user=str(os.getuid())+':'+str(os.getgid())
            if expected_existing_user is not None:
                # Existing-object comparison only. This never changes the host
                # process groups, Docker Config.User, or new-create environment.
                canonical=(isinstance(expected_existing_user,str) and len(expected_existing_user)<=32
                    and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*',expected_existing_user) is not None)
                cid=self.state.get('router_cid') if self.state else None
                if (not canonical or int(expected_existing_user.split(':')[0])!=os.getuid()
                        or not isinstance(cid,str) or re.fullmatch('[0-9a-f]{64}',cid) is None):
                    raise Failure('EXISTING_ROUTER_USER_UNCONFIRMED','Canonical nonroot owner identity and existing recorded CID required')
            self.expected_existing_user=current_user if expected_existing_user is None else expected_existing_user
            self.existing_user_override=expected_existing_user is not None
            self.env={'PATH':'/usr/bin:/bin','HOME':str(Path.home()),'LANG':'C.UTF-8',
                      'PROJECT_ROOT':str(self.repo),'LOCAL_UID':str(os.getuid()),'LOCAL_GID':str(os.getgid())}
        except Exception as exc:
            self.step="private_metadata_initialization"
            self.event("failed",exit_code=1,error_code=getattr(exc,"code",type(exc).__name__))
            print(json.dumps({"status":"FAILED","log":str(self.log_path),"exit_code":1}),file=sys.stderr)
            self.log.close()
            raise

    def event(self,event,**data):
        self.log.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                   'step':self.step,'event':event,
                                   'elapsed_seconds':round(time.monotonic()-self.started,3),**data})+'\n');self.log.flush()

    def enter(self,step):
        self.step=step;self.event('begin')
        limit=' (HTTP confirmation: maximum 90 seconds)' if step in ['readonly_router_gate','readonly_resident_gate'] else ''
        print('[+%.1fs] %s%s'%(time.monotonic()-self.started,step,limit),file=sys.stderr,flush=True)

    def save(self,phase,**values):
        self.state.update(phase=phase,**values)
        p=self.root/('host-state-'+uuid.uuid4().hex+'.tmp')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(self.state,f);f.flush();os.fsync(f.fileno())
        os.replace(p,self.state_path);self.event('state',phase=phase)

    def command(self,args,timeout=15,check=True,capture_log=False):
        remaining=(self.recovery_deadline-time.monotonic()) if self.recovery_deadline is not None else 420-(time.monotonic()-self.started)
        if remaining<=0:raise Failure('MAINTENANCE_DEADLINE','Maintenance deadline reached')
        command_started=time.monotonic()
        try:r=self.execute(args,env=self.env,capture_output=True,text=True,timeout=min(timeout,remaining))
        except subprocess.TimeoutExpired:
            self.event('command_timeout',exit_code=124)
            raise Failure('COMMAND_OUTCOME_UNKNOWN','Command timed out; inspect actual state before continuing',124)
        except OSError as exc:raise Failure('COMMAND_UNAVAILABLE',type(exc).__name__)
        self.event('command_end',exit_code=r.returncode,duration_seconds=round(time.monotonic()-command_started,3))
        if capture_log:self.event('diagnostic',text=(r.stdout+r.stderr)[-6000:])
        if check and r.returncode:
            self.event('diagnostic',text=r.stderr[-2500:])
            raise Failure('COMMAND_FAILED','Fixed maintenance step failed',r.returncode)
        return r

    def docker(self,*args,**kwargs):
        return self.command(['/usr/bin/docker','--host','unix:///var/run/docker.sock',*args],**kwargs)

    def inspect(self,identity):
        self.event('docker_read_target',target=identity)
        r=self.docker('inspect',identity,check=False)
        if r.returncode:
            message=r.stderr.lower()
            if 'permission denied' in message:
                self.event('diagnostic',text=r.stderr[-2000:])
                try:
                    sock=Path('/var/run/docker.sock').stat()
                    self.event('socket_permission',uid=os.getuid(),group_ids=os.getgroups(),socket_uid=sock.st_uid,socket_gid=sock.st_gid,socket_mode=oct(stat.S_IMODE(sock.st_mode)))
                except OSError:pass
                raise Failure('DOCKER_PERMISSION_DENIED','Current process cannot access the fixed Docker socket; no privilege/group/context change attempted')
            if 'no such object' in message or 'no such container' in message:return None
            self.event('diagnostic',text=r.stderr[-2000:])
            raise Failure('DOCKER_READ_FAILED','Docker read unavailable; no automatic privilege change')
        data=json.loads(r.stdout)
        if not isinstance(data,list) or len(data)!=1:raise Failure('AMBIGUOUS_OBJECT','Expected one Docker object')
        return data[0]

    def original(self):
        value=self.inspect(self.original_id)
        if not value or value.get('Id')!=self.original_id or value.get('Name')!=ORIGINAL or value.get('Image')!=IMAGE:
            raise Failure('ORIGINAL_ID_MISMATCH','Saved original CID/name/image differs; no mutation')
        fingerprint=hashlib.sha256(json.dumps({k:value[k] for k in ['Config','HostConfig']},sort_keys=True).encode()).hexdigest()
        if self.state and self.state.get('original_fingerprint')!=fingerprint:
            raise Failure('ORIGINAL_CONFIG_CHANGED','Original configuration changed; stop for review')
        return value,fingerprint

    def owned_router(self):
        value=self.inspect(ROUTER)
        if not value:return None
        if not self.state:raise Failure('UNMANAGED_ROUTER','Router exists without ownership state; never adopt or overwrite')
        labels=value.get('Config',{}).get('Labels',{})
        if (value.get('Image')!=IMAGE or value.get('Name')!='/'+ROUTER or
            labels.get('com.docker.compose.project')!=PROJECT or labels.get('io.aceis.deployment')!=self.state['token'] or
            self.state.get('router_cid') not in [None,value.get('Id')]):
            raise Failure('ROUTER_OWNERSHIP_MISMATCH','Router generation is unknown; do not stop or replace it')
        h=value.get('HostConfig',{})
        mounts={m.get('Destination'):m for m in value.get('Mounts',[]) if m.get('Type')=='bind'}
        expected_mounts={'/models':(str(self.repo/'models'),False), '/cache':(str(self.repo/'.cache/large-coder-b3/runtime'),True),
                         '/config/models.ini':(str(self.llm/'integration/router-presets.PROPOSAL.ini'),False)}
        if (h.get('Memory')!=34359738368 or h.get('MemorySwap')!=34359738368 or h.get('NanoCpus')!=8000000000 or
            h.get('PidsLimit')!=512 or h.get('ReadonlyRootfs') is not True or h.get('Privileged') is not False or
            h.get('CapDrop')!=['ALL'] or h.get('CapAdd') not in [None,[]] or 'no-new-privileges:true' not in h.get('SecurityOpt',[]) or
            h.get('PortBindings')!={'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]} or
            value.get('Config',{}).get('User')!=self.expected_existing_user or
            value.get('Path')!='/app/llama-server' or value.get('Args')!=ROUTER_ARGS or
            set(value.get('NetworkSettings',{}).get('Networks',{}))!={'project-kiss-large-coder-b3_local'} or
            set(mounts)!=set(expected_mounts) or any((mounts[k].get('Source'),mounts[k].get('RW'))!=v for k,v in expected_mounts.items())):
            raise Failure('ROUTER_CONTRACT_MISMATCH','Owned router resource/security/path contract differs; do not start it')
        return value

    def human_guard(self):
        self.enter('human_host_guard')
        if not sys.stdin.isatty():raise Failure('HUMAN_TERMINAL_REQUIRED','Run with bash in your normal host terminal; not Codex or source')
        sys.path.insert(0,str(Path(self.profile['orchestrator_root'])/'src'))
        from isolation_guard import require_isolation_creation
        try:context=require_isolation_creation('human-router-maintenance')
        except RuntimeError as exc:
            self.event('guard_evidence',evidence=getattr(exc,'evidence',{'state':'UNKNOWN'}))
            raise Failure('HOST_CONTEXT_UNCONFIRMED','Host context not confirmed; no bypass or deployment')
        self.event('host_context',context=context)

    def lock(self,rollback=False):
        self.enter('common_generation_lock')
        if not rollback and (self.root/'UNCERTAIN.json').exists():raise Failure('PRIOR_UNKNOWN','Existing inference/lifecycle uncertainty requires inspection')
        self.lock_fd=os.open(self.root/'generation.lock',os.O_RDWR|os.O_NOFOLLOW)
        try:fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Failure('BUSY','Active generation or maintenance; nothing was stopped')

    def idle_coordinator(self):
        self.enter('coordinator_idle')
        sys.path.insert(0,str(Path(self.profile['orchestrator_root'])/'src'))
        from control_socket import request
        raw=request(Path(self.profile['orchestrator_root'])/'.runtime/development-poc-e32-c00a7a45','status')
        if raw.get('active_tasks') or raw.get('blocked') or raw.get('pending_recovery') or raw.get('stopping') or raw.get('paused') or any(raw.get('task_counts',{}).get(k,0) for k in ['QUEUED','RUNNING','VERIFYING']):
            raise Failure('COORDINATOR_BUSY','Coordinator has pending work; nothing was stopped')

    def gate(self,mode):
        self.enter('readonly_'+mode+'_gate')
        args=['/usr/bin/python3','-B',str(self.llm/'integration/host_deployment_check.py'),mode]
        if mode=='router' and self.internal_route:args.append('--candidate')
        r=self.command(args,timeout=100,check=False,capture_log=True)
        if r.returncode:
            try:diagnostic=json.loads(r.stdout)
            except (ValueError,TypeError):diagnostic={}
            self.event('gate_failure',diagnostic=diagnostic)
            raise Failure('READONLY_GATE_FAILED','Read-only gate: '+str(diagnostic.get('reason','invalid diagnostic'))+' '+str(diagnostic.get('endpoint','')),r.returncode)
        return r

    def network(self,strict=False):
        rows=json.loads(self.docker('network','inspect',endpoint_config.NETWORK).stdout)
        if len(rows)!=1 or rows[0].get('Internal') is not True or rows[0].get('Driver')!='bridge':
            raise Failure('NETWORK_CONTRACT_MISMATCH','Existing internal bridge required; no automatic network change')
        network=rows[0]
        if strict:
            expected=self.profile.get('internal_network_id')
            if (not isinstance(expected,str) or re.fullmatch('[0-9a-f]{64}',expected) is None or
                network.get('Id')!=expected or network.get('Name')!=endpoint_config.NETWORK):
                raise Failure('NETWORK_ID_MISMATCH','Human-approved existing network ID required')
            peers=network.get('Containers')
            if not isinstance(peers,dict) or set(peers)-{self.state.get('router_cid')}:
                raise Failure('NETWORK_PEER_UNCONFIRMED','Unexpected connected peer; no peer is stopped or adopted')
        return network

    def route_precheck(self):
        for name,candidate in [('router-candidate.json',True),('router-deployment.json',False)]:
            path=self.root/name
            if os.path.lexists(path):
                try:endpoint_config.validate_receipt(endpoint_config.private_json(path),self.root,candidate=candidate,phase_check=False)
                except (OSError,ValueError,TypeError,KeyError) as exc:
                    raise Failure('ROUTE_METADATA_UNSAFE','Existing route must be reviewed; not overwritten') from exc

    def capture_internal_route(self,verify_only=False):
        self.enter('verify_router_internal_endpoint')
        router=self.owned_router();network=self.network(strict=True)
        if not router or not router.get('State',{}).get('Running'):
            raise Failure('ROUTER_NOT_RUNNING','Owned router stopped before HTTP gate')
        ports=router['NetworkSettings'].get('Ports',{})
        if not isinstance(ports,dict) or any(k!='8080/tcp' or v not in (None,[],[{'HostIp':'127.0.0.1','HostPort':'8080'}]) for k,v in ports.items()):
            raise Failure('PORT_SCOPE_CHANGED','Unexpected runtime published port; no connection')
        ep=router['NetworkSettings']['Networks'][endpoint_config.NETWORK]
        peer=network['Containers'].get(router['Id'])
        if (ep.get('NetworkID')!=network['Id'] or not isinstance(peer,dict) or
            not re.fullmatch('[0-9a-f]{64}',ep.get('EndpointID','')) or peer.get('EndpointID')!=ep['EndpointID']):
            raise Failure('ENDPOINT_ID_MISMATCH','Network and owned container endpoint differ')
        try:
            address=ipaddress.IPv4Address(ep['IPAddress'])
            candidates=[ipaddress.ip_network(c['Subnet'],strict=True) for c in network['IPAM']['Config'] if ':' not in c.get('Subnet','')]
            subnets=[n for n in candidates if address in n]
            if len(subnets)!=1 or not any(subnets[0].subnet_of(n) for n in endpoint_config.RFC1918):raise ValueError('Private subnet required')
            subnet=subnets[0]
            if (address in (subnet.network_address,subnet.broadcast_address) or ep.get('IPPrefixLen')!=subnet.prefixlen or
                peer.get('IPv4Address')!=str(address)+'/'+str(subnet.prefixlen)):
                raise ValueError('Network peer address differs')
        except (ValueError,TypeError,KeyError) as exc:
            raise Failure('ENDPOINT_IP_MISMATCH','Owned private IPv4/subnet not confirmed') from exc
        data={'schema':2,'mode':'router','human_deployment_confirmed':False,'image':IMAGE,
              'container_id':router['Id'],'deployment_token':self.state['token'],
              'network_name':endpoint_config.NETWORK,'network_id':network['Id'],'subnet':str(subnet),
              'ipv4':str(address),'port':8080,'endpoint_id':ep['EndpointID'],
              'registry_sha256':endpoint_config.digest(self.root),'original_fingerprint':self.state['original_fingerprint'],
              'checked_at':time.time(),'contract':endpoint_config.CONTRACT}
        if verify_only:
            if not self.candidate or any(data[k]!=self.candidate[k] for k in data if k!='checked_at'):
                raise Failure('ENDPOINT_CHANGED','Owned route changed during GET gate; no publication')
            return
        self.save(self.state['phase'],route_ipv4=str(address),route_subnet=str(subnet),
                  route_network_id=network['Id'],route_endpoint_id=ep['EndpointID'])
        endpoint_config.validate_receipt(data,self.root,candidate=True)
        endpoint_config.atomic_private(self.root/'router-candidate.json',data)
        self.candidate=data
        self.event('verified_internal_endpoint',ipv4=str(address),network_id=network['Id'],endpoint_id=ep['EndpointID'])

    def retire_routes(self):
        self.route_precheck()
        for name in ['router-deployment.json','router-candidate.json']:
            path=self.root/name
            if os.path.lexists(path):
                saved=self.root/(name+'.retired-'+str(time.time_ns()))
                os.rename(path,saved);self.event('route_retired',file=name)

    def publish_route(self):
        self.capture_internal_route(verify_only=True)
        data={**self.candidate,'human_deployment_confirmed':True,'checked_at':time.time()}
        self.save('DEPLOYED')
        endpoint_config.validate_receipt(data,self.root)
        self.retire_routes()
        endpoint_config.atomic_private(self.root/'router-deployment.json',data)
        self.event('route_published',container_id=data['container_id'],ipv4=data['ipv4'])

    def router_gate(self):
        if self.internal_route:self.capture_internal_route()
        else:self.verify_published_router_port()
        self.gate('router')
        if self.internal_route:self.publish_route()
        else:self.save('DEPLOYED')

    def verify_published_router_port(self):
        self.enter('verify_router_published_port')
        router=self.owned_router()
        if not router or not router.get('State',{}).get('Running'):
            raise Failure('ROUTER_NOT_RUNNING','Owned router stopped before HTTP gate')
        ports=router.get('NetworkSettings',{}).get('Ports')
        expected=[{'HostIp':'127.0.0.1','HostPort':'8080'}]
        if not isinstance(ports,dict) or ports.get('8080/tcp')!=expected:
            self.event('publication_missing',requested=expected,observed=ports)
            raise Failure('ROUTER_PORT_UNPUBLISHED','Requested loopback port is not realized; no network/security fallback')

    def verify_preset(self):
        self.enter('fixed_three_model_preset')
        cfg=configparser.ConfigParser(interpolation=None)
        cfg.read(self.llm/'integration/router-presets.PROPOSAL.ini')
        fixed={'kiss-qwen3-coder-30b':('/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf',99,True),
               'kiss-b3-gpt-oss-120b':('/models/large-coder-b3/gpt-oss-120b/gpt-oss-120b-MXFP4.gguf',20,False),
               'kiss-b3-qwen-coder-next':('/models/large-coder-b3/qwen-coder-next/Qwen3-Coder-Next-Q4_K_M-00001-of-00004.gguf',28,False)}
        allowed={'model','alias','load-on-startup','ctx-size','parallel','n-gpu-layers','fit','batch-size','ubatch-size','threads','threads-batch','no-ui','cache-type-k','cache-type-v','flash-attn','load-mode','lazy-mode','no-context-shift','jinja','reasoning-format','reasoning-effort','chat-template-kwargs','metrics','offline'}
        if set(cfg.sections())!=set(fixed) or cfg.defaults():raise Failure('PRESET_MISMATCH','Exactly three approved preset sections required')
        for name,(model,layers,startup) in fixed.items():
            row=cfg[name]
            if (set(row)-allowed or row.get('model')!=model or row.get('alias')!=name or row.getint('n-gpu-layers')!=layers or
                row.getint('ctx-size')!=32768 or row.getint('parallel')!=1 or row.get('fit')!='off' or row.getboolean('load-on-startup')!=startup):
                raise Failure('PRESET_MISMATCH','Fixed model/path/context/offload contract differs')

    def device_check(self):
        self.enter('device_metadata')
        a=Path('/dev/kfd').stat().st_gid;b=Path('/dev/dri/renderD128').stat().st_gid
        if a!=b:raise Failure('GPU_GROUP_MISMATCH','Existing GPU group metadata differs')
        self.env['GPU_GID']=str(a)

    def compose(self,*args,**kwargs):
        if self.existing_user_override:
            raise Failure('EXISTING_USER_RECOVERY_ONLY','Existing-user expectation cannot be used for Compose operations')
        return self.docker('compose','-f',str(self.llm/'integration/router-compose.PROPOSAL.yaml'),*args,**kwargs)

    def deploy(self,resume=False,internal_route=False):
        if self.existing_user_override:
            raise Failure('EXISTING_USER_RECOVERY_ONLY','Existing-user expectation cannot be used for deployment')
        self.internal_route=internal_route
        self.human_guard();self.lock();self.idle_coordinator();self.device_check();self.verify_preset()
        self.enter('inspect_original_and_router');original,fingerprint=self.original();router=self.owned_router()
        if self.state and self.state.get('phase') in ['FAILED','ROLLED_BACK','ROLLBACK_FAILED'] and not resume:
            raise Failure('EXPLICIT_RESUME_REQUIRED','Read the previous log; use --resume only after reviewing its cause')
        if self.state is None:
            # Existing unrecorded legacy CID metadata is not silently ignored.
            legacy=self.root/'router-host-maintenance.cid'
            if legacy.exists():raise Failure('LEGACY_PARTIAL_STATE','Legacy CID record requires read-only reconciliation; do not create another router')
            self.state={'schema':1,'token':uuid.uuid4().hex,'resident_cid':self.original_id,'router_cid':None,
                        'original_fingerprint':fingerprint,'phase':'INITIAL'}
            self.save('INITIAL')
        self.env['ROUTER_DEPLOYMENT_TOKEN']=self.state['token']
        self.enter('verify_existing_internal_network')
        self.network(strict=internal_route)
        if internal_route:
            self.route_precheck()
            self.retire_routes()
        if router and router['State']['Running']:
            self.deployment_started=True
            if original['State']['Running']:raise Failure('BOTH_RUNNING','Both objects running; use owned rollback, not another deployment')
            self.router_gate();return
        if original['State']['Running']:self.gate('preflight')
        elif not router:raise Failure('ORIGINAL_STOPPED_NO_ROUTER','Original stopped and no router exists; run rollback first')
        if router is None:
            if self.state.get('router_cid'):raise Failure('RECORDED_ROUTER_MISSING','Known router is missing; no automatic second create')
            self.enter('compose_configuration');self.compose('config','--quiet')
            self.enter('create_router');self.save('CREATE_INTENT')
            self.compose('create','--no-build','--pull','never','router',timeout=90)
            router=self.owned_router()
            if not router:raise Failure('CREATE_UNCONFIRMED','Create returned without a verifiable router')
            self.save('CREATED',router_cid=router['Id'])
        elif not self.state.get('router_cid'):self.save('CREATED',router_cid=router['Id'])
        self.deployment_started=True
        if original['State']['Running']:
            self.enter('stop_original');self.save('STOP_ORIGINAL_INTENT')
            self.docker('stop','--timeout','30',self.original_id,timeout=40)
        self.enter('verify_original_stopped')
        original,_=self.original()
        if original['State']['Running']:raise Failure('STOP_UNCONFIRMED','Original is still running; do not start router')
        self.save('ORIGINAL_STOPPED')
        self.enter('start_owned_router');self.save('START_ROUTER_INTENT')
        self.docker('start',router['Id'],timeout=30)
        self.router_gate()

    def rollback(self,automatic=False):
        self.recovery_deadline=time.monotonic()+150
        if not automatic:self.human_guard();self.lock(rollback=True)
        self.enter('rollback_identity');original,_=self.original();router=self.owned_router()
        if not self.state:
            if original['State']['Running']:self.gate('resident');return
            raise Failure('NO_OWNERSHIP_RECORD','No deployment record; manual identity review required')
        self.retire_routes()
        self.save('ROLLBACK_INTENT')
        if router and router['State']['Running']:
            self.enter('rollback_stop_owned_router');self.docker('stop','--timeout','20',router['Id'],timeout=30)
            observed=self.owned_router()
            if observed and observed['State']['Running']:raise Failure('ROUTER_STOP_UNCONFIRMED','Router stop not confirmed; original not started')
        original,_=self.original()
        if not original['State']['Running']:
            self.enter('rollback_start_original');self.docker('start',self.original_id,timeout=30)
        self.gate('resident');self.save('ROLLED_BACK')
        # No object, credential, model, state or UNKNOWN marker is removed.

    def close(self):
        if self.lock_fd is not None:os.close(self.lock_fd)
        self.log.close()


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv not in [['deploy'],['resume'],['deploy-internal'],['resume-internal'],['rollback']]:
        print('Use the deploy_router.sh or rollback_router.sh wrapper.',file=sys.stderr);return 64
    os.umask(0o077);task=None;exit_code=0
    try:
        task=Maintenance()
        if argv[0]=='rollback':task.rollback()
        else:task.deploy(resume=argv[0] in ['resume','resume-internal'],internal_route=argv[0] in ['deploy-internal','resume-internal'])
        task.event('finished',exit_code=0)
        print(json.dumps({'status':task.state['phase'] if task.state else 'ORIGINAL_HEALTHY','exit_code':0,'log':str(task.log_path),'generation_requests':0}))
    except (Exception, KeyboardInterrupt) as exc:
        raw=getattr(exc,'exit_code',130 if isinstance(exc,KeyboardInterrupt) else 1) or 1
        exit_code=(128-raw) if raw<0 else raw
        if task:
            failed_step=task.step;code=getattr(exc,'code',type(exc).__name__)
            task.event('failed',failed_step=failed_step,error_code=code,exit_code=exit_code,message=str(exc)[:500])
            rollback='NOT_NEEDED'
            if argv[0]!='rollback' and task.deployment_started:
                try:
                    owned=task.owned_router()
                    if owned:task.docker('logs','--since',task.log_since,'--timestamps','--tail','50',owned['Id'],timeout=5,check=False,capture_log=True)
                except Exception:pass
                try:task.rollback(automatic=True);rollback='RESTORED_ORIGINAL'
                except Exception as recovery:
                    rollback='FAILED';task.event('rollback_failed',error_code=getattr(recovery,'code',type(recovery).__name__))
                    if task.state:task.save('ROLLBACK_FAILED',last_failed_step=failed_step,last_exit_code=exit_code)
            elif task.state:
                task.save('FAILED',last_failed_step=failed_step,last_exit_code=exit_code)
            print(json.dumps({'status':'FAILED','failed_step':failed_step,'error_code':code,'exit_code':exit_code,'rollback':rollback,'log':str(task.log_path)}),file=sys.stderr)
        else:print(json.dumps({'status':'FAILED','step':'private_metadata_initialization','error_code':getattr(exc,'code',type(exc).__name__),'exit_code':exit_code}),file=sys.stderr)
    finally:
        if task:task.close()
    return min(255,max(0,exit_code))

if __name__=='__main__':raise SystemExit(main())
