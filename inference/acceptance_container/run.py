"""Explicit isolated EVO acceptance, never a production deployment/Quick Start.

Historical EVO-X3 harness: SOURCE below points to an older frozen snapshot.
This module does not accept this integrated checkout as its runtime source.
Do not execute it as current-tree acceptance without a separately reviewed adapter.

Default is a non-disruptive plan. --execute performs only the named maintenance
and fixed containers below. Interrupted downloads are never automatically replayed.
"""
from __future__ import annotations
import argparse,datetime,fcntl,hashlib,http.client,json,os,pathlib,re,signal,socket,stat,subprocess,threading,time,urllib.request,urllib.parse
from inference.aceis_service.core import snapshot,check_resources,GIB,ServiceError
from inference.aceis_service.host_supervisor import HostSupervisor,OwnedCoreStop
from inference.local_platform.model_management import ModelManager,OllamaAdapter,read_catalog,read_private_json,FIELDS,ModelError
from .engine import FixedContainerHTTP,docker,IMAGE,fixed_engine_identity

ROOT=pathlib.Path('/home/y-ooya/laf-expanded-acceptance-20261108')
SOURCE=ROOT/'candidate'; RUN=ROOT/'integration-runtime'; EVID=RUN/'evidence'
PROVIDER=RUN/'provider'; WEIGHTS=RUN/'weights'; HOST=RUN/'host'; CORE=RUN/'core'
NAME_PROVIDER='laf-acceptance-ollama-20261108'; NAME_CORE='laf-acceptance-core-20261108'
NETWORK='project-kiss-large-coder-b3_local'; HISTORICAL=pathlib.Path('/home/y-ooya/workspace/project-kiss-infra/agents/local_llm/.runtime/generation.lock')
ROUTER_SOCKET='/run/user/1000/aceis-inference/service.sock'; NPU_DIR='/run/user/1000/aceis-npu'
ORIGINAL_PROVIDER='5521b5156a45782620c3cdf0d3b2cca5574deea815a50b3dc4b6e868958d7252'
ORCH=pathlib.Path('/home/y-ooya/src/agent-orchestrator'); ORCH_RUNTIME=ORCH/'.runtime/development-poc-e32-c00a7a45'
BASE='project-kiss-code-eval@sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c'
TAG='laf-core-local:integrated-acceptance-20261108'
PRODUCTION={pathlib.Path('/home/y-ooya/.config/systemd/user/aceis-inference.service'):'946b3961a6866c1fb3a7402dbe5b671fdb404371a907a6eabb4a9d072f4234a9',pathlib.Path('/home/y-ooya/.config/systemd/user/aceis-inference.service.d/20-independent-npu-api.conf'):'9930577fab3c1f75725fa3690610a3b08f3552cf5609136f35799e1b3cbd35db',pathlib.Path('/home/y-ooya/.local/state/aceis-inference/config.json'):'1bb20bf34bd96eef0f6171bf1ca0675a45a394a2aa84254bc7f30c0b4a4d7791'}


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(path,value):
    raw=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    with open(path,'w',encoding='utf-8') as f:os.chmod(path,0o600);f.write(raw);f.flush();os.fsync(f.fileno())
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()
def command(*args,timeout=30):return subprocess.check_output(args,text=True,timeout=timeout).strip()
def private(path):
    path.mkdir(mode=0o700,parents=False,exist_ok=True)
    s=path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700 or path.is_symlink():raise ServiceError('private owned run directory required')
    return path
class UDS(http.client.HTTPConnection):
    def __init__(self,path,timeout=5):super().__init__('localhost',timeout=timeout);self.path=str(path)
    def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect(self.path)
def request(path,method,route,body=None,timeout=5):
    from inference.local_platform.cli import checked_socket
    c=UDS(checked_socket(path),timeout)
    try:
        c.request(method,route,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json'})
        r=c.getresponse(); raw=r.read(2*1024**2+1)
        if len(raw)>2*1024**2:raise ServiceError('response bound exceeded')
        value=json.loads(raw)
        if r.status>=400:raise ServiceError('private API error '+str(r.status)+': '+str(value)[:300])
        return value
    finally:c.close()
def health(path):return request(path,'GET','/health')
def orch(method):return json.loads(command('python3','-B',str(ORCH/'src/runner.py'),'--runtime',str(ORCH_RUNTIME),'--development-poc',method))
def production_hashes():
    value={str(p):digest(p) for p in PRODUCTION}
    if any(value[str(p)]!=h for p,h in PRODUCTION.items()):raise ServiceError('production hash mismatch; no changes allowed')
    return value

def wait_until(fn,seconds,label):
    deadline=time.monotonic()+seconds; last=None
    while time.monotonic()<deadline:
        try:
            result=fn()
            if result:return result
        except (OSError,ValueError,http.client.HTTPException,ServiceError,ModelError) as e:last=str(e)
        time.sleep(.5)
    raise ServiceError(label+' timed out'+(' ('+last+')' if last else ''))
def physical_idle():
    consecutive=0
    def sample():
        nonlocal consecutive
        s=snapshot();check_resources(s,s)
        consecutive=consecutive+1 if s['vram_used']<3*GIB else 0
        return s if consecutive>=2 else None
    return wait_until(sample,35,'two-sample physical GPU idle')

def recheck_manifests(catalog):
    out=[]
    for item in catalog:
        req=urllib.request.Request(item['source'],headers={'User-Agent':'LAF-isolated-acceptance/1.0'})
        with urllib.request.urlopen(req,timeout=30) as r:
            if r.url!=item['source']:raise ServiceError('model manifest redirected unexpectedly')
            raw=r.read(1024*1024+1)
        if len(raw)>1024*1024 or 'sha256:'+hashlib.sha256(raw).hexdigest()!=item['digest']:raise ServiceError('official manifest changed; pull not attempted')
        value=json.loads(raw)
        if value.get('schemaVersion')!=2 or not isinstance(value.get('layers'),list):raise ServiceError('unexpected model manifest')
        out.append({'id':item['id'],'source':item['source'],'digest':item['digest'],'utc':utc(),'manifest':value,'raw_bytes':len(raw)})
    return out

def store_snapshot(manifests):
    store=PROVIDER/'store';items={};expected_links={}
    for m in manifests:
        parsed=urllib.parse.urlsplit(m['source']);parts=parsed.path.split('/')
        if parsed.hostname!='registry.ollama.ai' or len(parts)!=6 or parts[1:3]!=['v2','library'] or parts[4]!='manifests':raise ServiceError('unexpected official manifest source')
        relative='manifests-v2/ollama.com/library/'+parts[3]+'/'+parts[5]
        expected_links[relative]='../../../../blobs/'+m['digest'].replace(':','-')
    for path in sorted(store.rglob('*')):
        entry=path.lstat();relative=str(path.relative_to(store))
        if entry.st_uid!=os.getuid():raise ServiceError('unexpected model store owner')
        if stat.S_ISDIR(entry.st_mode):continue
        common={'inode':entry.st_ino,'dev':entry.st_dev,'mtime_ns':entry.st_mtime_ns}
        if stat.S_ISLNK(entry.st_mode):
            # Never follow an arbitrary store link. Only the two verified v2 tag
            # links, with exactly the documented relative target, are permitted.
            target=os.readlink(path)
            if relative not in expected_links or target!=expected_links[relative] or entry.st_nlink!=1:raise ServiceError('unexpected model store symlink')
            items[relative]={'type':'verified_manifest_symlink','target':target,'bytes':entry.st_size,**common}
        elif stat.S_ISREG(entry.st_mode):
            if entry.st_nlink!=1:raise ServiceError('unexpected hardlinked model store file')
            items[relative]={'type':'regular_file','bytes':entry.st_size,'sha256':digest(path),**common}
        else:raise ServiceError('unexpected model store entry')
    for m in manifests:
        descriptors=[m['manifest']['config'],*m['manifest']['layers'],{'digest':m['digest'],'size':m['raw_bytes']}]
        for desc in descriptors:
            name='blobs/'+desc['digest'].replace(':','-');found=items.get(name)
            if found is None or found['type']!='regular_file' or found['bytes']!=desc['size'] or 'sha256:'+found['sha256']!=desc['digest']:raise ServiceError('downloaded model blob identity/size mismatch')
    for relative,target in expected_links.items():
        if relative not in items or items[relative].get('type')!='verified_manifest_symlink' or items[relative].get('target')!=target:raise ServiceError('verified v2 manifest link absent or wrong type')
    info=store.stat()
    return {'root':str(store),'root_inode':info.st_ino,'root_dev':info.st_dev,'files':items,'total_bytes':sum(v['bytes'] for v in items.values())}


def completed_download_resume(catalog,manifests):
    prior=read_private_json(RUN/'evidence/journal.json')
    if not isinstance(prior,list) or not prior or prior[-1].get('stage')!='scheduler_restored':raise ServiceError('prior run restoration not confirmed; do not resume')
    if any(x.get('stage') in {'job_submitted','inference_completed','runtime_ready','npu_classified'} for x in prior):raise ServiceError('prior runtime outcome exists; this is not a download-only resume')
    restored=[x for x in prior if x.get('stage')=='production_restored']
    failures=[x for x in prior if x.get('stage')=='acceptance_failed']
    if not restored or len(failures)!=1 or failures[0].get('error')!='ServiceError: unexpected model store entry':raise ServiceError('unsupported prior failure; explicit reconciliation required')
    installed={x['model']:x['record'] for x in prior if x.get('stage')=='model_installed'}
    manager=ModelManager(RUN/'registry',catalog);value=manager._read()
    scope={'engine':fixed_engine_identity(NAME_PROVIDER,str(PROVIDER),PROVIDER/'store'),'model_store':str(PROVIDER/'store'),'generation_lock':str(HISTORICAL)}
    if value['pending'] is not None or value['scope']!=scope or set(value['models'])!={x['id'] for x in catalog}:raise ServiceError('complete matching managed registry required; no pull is allowed')
    for item in catalog:
        record=value['models'][item['id']]
        if installed.get(item['id'])!=record or any(record.get(k)!=item[k] for k in FIELDS) or record.get('status')!='installed':raise ServiceError('prior installed model differs from verified resume catalog')
    return store_snapshot(manifests),digest(RUN/'registry/models.json')


class Run:
    def __init__(self,catalog,resume=False):
        self.resume=resume;self.catalog=catalog; self.ids={x['id'] for x in catalog};self.refs={x['reference'] for x in catalog}
        self.provider=None;self.core=None;self.adapter=None;self.sup=None;self.policy=None
        self.paused_by_us=False;self.router_stopped=False;self.monitor_stop=threading.Event();self.fault=None;self.baseline=None;self.events=[];self.original=None;self.image=None;self.stop_intent=False;self.restore_started=False;self.restore_submission_requested=False;self.restore_job=None;self.restore_deadline=None;self.in_cleanup=False;self.diagnostic_errors=[];self.pause_intent=False;self.original_scheduler_paused=None;self.provider_create_pending=None;self.core_create_pending=False;self.monitor_ready=threading.Event()
    def event(self,stage,**values):
        value={'utc':utc(),'stage':stage,**values};self.events.append(value)
        try:
            write(EVID/'journal.json',self.events)
            print(json.dumps(value,ensure_ascii=False),flush=True)
        except (OSError,ValueError) as exc:
            self.diagnostic_errors.append('journal/output: '+str(exc))
            if not self.in_cleanup:raise
    def diagnostic(self,action):
        try:action()
        except Exception as exc:self.diagnostic_errors.append(type(exc).__name__+': '+str(exc))
    def monitor(self):
        try:
            with open(EVID/'resources.jsonl','a') as f:
                os.chmod(EVID/'resources.jsonl',0o600);self.monitor_ready.set()
                while not self.monitor_stop.wait(1):
                    s=snapshot();f.write(json.dumps({'utc':utc(),**s})+'\n');f.flush()
                    if self.baseline:check_resources(s,self.baseline)
        except Exception as exc:
            self.fault=type(exc).__name__+': '+str(exc);self.monitor_ready.set()
            if self.sup is None and self.adapter is not None:
                try:
                    info=self.adapter.inspect()
                    if info['State']['Running']:docker('stop','-t','3',self.adapter.cid,timeout=15)
                except Exception:pass
    def check(self):
        if self.fault:raise RuntimeError('resource monitor fault: '+self.fault)
        if self.baseline:check_resources(snapshot(),self.baseline)
    def adapter_for(self,cid,network):
        return FixedContainerHTTP(cid,name=NAME_PROVIDER,owner=str(PROVIDER),provider_root=PROVIDER,weights=WEIGHTS,network=network,references=self.refs)
    def create_provider(self,network):
        if docker('ps','-aq','--filter','name=^/'+NAME_PROVIDER+'$'):raise ServiceError('disposable provider name already exists; no adoption')
        args=['create','--pull=never','--name',NAME_PROVIDER,'--label','aceis.inference.owner='+str(PROVIDER),'--memory','32g','--memory-swap','32g','--cpus','8','--pids-limit','512','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=512m','--ipc','private','--network',network,'--user','1000:1000','--device','/dev/kfd','--device','/dev/dri/renderD128','--group-add','990','--cap-drop','ALL','--security-opt','no-new-privileges:true','--init','--restart','no','--log-opt','max-size=10m','--log-opt','max-file=2','--entrypoint','/bin/ollama']
        for source,dest,ro in [(WEIGHTS,'/weights',True),(PROVIDER/'input','/input',True),(PROVIDER/'store','/store',False)]:args+=['--mount',f'type=bind,source={source},target={dest}'+(',readonly' if ro else '')]
        env={'HOME':'/tmp','OLLAMA_HOST':'0.0.0.0:30000','OLLAMA_MODELS':'/store','OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_NUM_PARALLEL':'1','OLLAMA_CONTEXT_LENGTH':'8192','OLLAMA_FLASH_ATTENTION':'1','OLLAMA_KEEP_ALIVE':'-1','OLLAMA_NO_CLOUD':'1','OLLAMA_NOPRUNE':'1','OLLAMA_NOHISTORY':'1'}
        for k,v in env.items():args+=['--env',k+'='+v]
        self.provider_create_pending=network;self.event('provider_create_requested',name=NAME_PROVIDER,network=network)
        try:cid=docker(*args,IMAGE,'serve')
        except Exception:
            found=docker('ps','-aq','--no-trunc','--filter','name=^/'+NAME_PROVIDER+'$')
            if found:
                self.provider=found;self.adapter=self.adapter_for(found,network);self.adapter.inspect();self.provider_create_pending=None;self.event('provider_create_outcome_reconciled',container_id=found)
            raise
        self.provider=cid;self.adapter=self.adapter_for(cid,network);self.adapter.inspect();self.provider_create_pending=None;self.event('provider_created',container_id=cid,network=network);return cid
    def start_provider(self):
        self.adapter.inspect();docker('start',self.provider)
        def ready():
            self.check(); v=self.adapter('GET','/api/version');return v if v.get('version')=='0.40.15' else None
        return wait_until(ready,45,'fixed provider readiness')
    def stop_provider(self):
        if not self.provider:return
        info=self.adapter.inspect()
        if info['State']['Running']:docker('stop','-t','3',self.provider,timeout=15)
        if self.adapter.inspect()['State']['Running']:raise ServiceError('provider termination unconfirmed')
        physical_idle()
    def remove_provider(self):
        self.stop_provider(); cid=self.provider
        def logs():
            out=subprocess.run(['docker','--host=unix:///var/run/docker.sock','logs',cid],capture_output=True,text=True,timeout=15)
            (EVID/('provider-'+cid[:12]+'.log')).write_text(out.stdout+out.stderr)
        self.diagnostic(logs)
        try:docker('rm',cid)
        except Exception:
            if docker('ps','-aq','--no-trunc','--filter','id='+cid):raise
        self.provider=None;self.adapter=None
        self.event('provider_removed',container_id=cid)
    def configure_core(self):
        config={'state_dir':'/core-state','runtime_dir':'/core-runtime','lifecycle_runtime_dir':'/host-lifecycle','npu_socket':'/npu-agent/service.sock','acceptance_ollama_profiles':[{'id':x['id'],'reference':x['reference'],'options':{'num_ctx':8192,'num_thread':4,'num_batch':128,'num_gpu':99,'temperature':0,'seed':42}} for x in self.catalog]}
        write(CORE/'config.json',config)
        mounts=[{'Source':str(HOST/'runtime'),'Destination':'/host-lifecycle','RW':False},{'Source':str(CORE/'state'),'Destination':'/core-state','RW':True},{'Source':str(CORE/'runtime'),'Destination':'/core-runtime','RW':True},{'Source':str(CORE/'config.json'),'Destination':'/config/core.json','RW':False},{'Source':NPU_DIR,'Destination':'/npu-agent','RW':False}]
        self.policy={'container_name':NAME_CORE,'image':self.image,'owner':str(RUN),'uid':1000,'gid':1000,'network':NETWORK,'memory':1024**3,'memory_swap':1024**3,'nano_cpus':2*10**9,'pids_limit':128,'mounts':mounts,'devices':[]}
        config_host={'state_dir':str(HOST/'state'),'runtime_dir':str(HOST/'runtime'),'generation_lock':str(HISTORICAL),'lease_seconds':30,'ollama':{'state_dir':str(PROVIDER),'weights':str(WEIGHTS),'container_name':NAME_PROVIDER,'docker_network':NETWORK},'core':self.policy}
        write(HOST/'config.json',config_host);return config_host
    def create_core(self):
        if docker('ps','-aq','--filter','name=^/'+NAME_CORE+'$'):raise ServiceError('disposable Core name already exists; no adoption')
        args=['create','--pull=never','--name',NAME_CORE,'--label','aceis.core.owner='+str(RUN),'--network',NETWORK,'--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--ipc','private','--memory','1g','--memory-swap','1g','--cpus','2','--pids-limit','128','--restart','no','--log-opt','max-size=10m','--log-opt','max-file=2']
        for m in self.policy['mounts']:args+=['--mount',f"type=bind,source={m['Source']},target={m['Destination']}"+(',readonly' if not m['RW'] else '')]
        self.core_create_pending=True;self.event('core_create_requested',name=NAME_CORE)
        try:cid=docker(*args,self.image,'--config','/config/core.json')
        except Exception:
            found=OwnedCoreStop(self.policy).inspect()
            if found:self.core=found[1]['Id'];self.core_create_pending=False;self.event('core_create_outcome_reconciled',container_id=self.core)
            raise
        self.core=cid
        guard=OwnedCoreStop(self.policy);info=guard.inspect()[1]
        if info['HostConfig'].get('GroupAdd') not in (None,[]) or info['HostConfig'].get('SecurityOpt')!=['no-new-privileges:true']:raise ServiceError('unexpected Core groups/security options')
        self.core_create_pending=False;write(EVID/('core-'+cid[:12]+'-inspect.json'),info);return cid
    def start_runtime(self,cycle):
        config=self.configure_core();self.create_core();self.sup=HostSupervisor(config,HOST/'config.json');self.sup.start();docker('start',self.core)
        def ready():
            self.check();info=OwnedCoreStop(self.policy).inspect()[1]
            if not info['State']['Running']:raise RuntimeError('Core exited before readiness; inspect retained logs')
            h=health(CORE/'runtime/service.sock');return h if h['status']=='ready' and h['fault'] is None else None
        value=wait_until(ready,150,'Core readiness');self.event('runtime_ready',cycle=cycle,health=value)
    def stop_runtime(self,cycle):
        oom=False
        if self.core:
            OwnedCoreStop(self.policy).stop()
            info=OwnedCoreStop(self.policy).inspect()[1];cid=self.core
            oom=bool(info['State'].get('OOMKilled'))
            self.diagnostic(lambda:write(EVID/('core-'+cid[:12]+'-state.json'),info['State']))
            def logs():
                out=subprocess.run(['docker','--host=unix:///var/run/docker.sock','logs',cid],capture_output=True,text=True,timeout=15)
                (EVID/('core-'+cid[:12]+'.log')).write_text(out.stdout+out.stderr)
            self.diagnostic(logs)
        if self.sup:self.sup.close();self.sup=None
        self.stop_provider();physical_idle()
        if self.core:
            cid=self.core
            try:docker('rm',cid)
            except Exception:
                if docker('ps','-aq','--no-trunc','--filter','id='+cid):raise
            self.core=None;self.event('core_removed',cycle=cycle,container_id=cid)
        if oom and not self.in_cleanup:raise ServiceError('Core was OOM killed; safety cleanup completed')
    def inference(self,item,cycle):
        self.check(); start=time.monotonic();body={'model':item['id'],'messages':[{'role':'user','content':'Write one short greeting.'}],'max_tokens':32,'timeout_seconds':120}
        # Exactly one submission. Unknown submission outcome is never replayed.
        submitted=request(CORE/'runtime/service.sock','POST','/v1/jobs',body);jid=submitted.get('id')
        if not isinstance(jid,str) or len(jid)!=32:raise ServiceError('unknown job submission outcome; do not replay')
        self.event('job_submitted',cycle=cycle,model=item['id'],job_id=jid)
        def finished():
            self.check();out=request(CORE/'runtime/service.sock','GET','/v1/jobs/'+jid)
            if out.get('id')!=jid or out.get('model')!=item['id']:raise ServiceError('job identity changed')
            return out if out.get('status') in {'completed','failed','cancelled'} else None
        result=wait_until(finished,125,'accepted inference job')
        if result['status']!='completed' or not result.get('result',{}).get('content','').strip():raise ServiceError('inference failed or empty output: '+str(result)[:500])
        running=self.adapter('GET','/api/ps')
        if len(running['models'])!=1 or running['models'][0]['name']!=item['reference'] or running['models'][0].get('size_vram',0)<=0:raise ServiceError('real inference GPU/loaded-model identity not confirmed')
        self.event('inference_completed',cycle=cycle,model=item['id'],seconds=time.monotonic()-start,result=result,engine_ps=running)
    def classify(self,cycle):
        from inference.aceis_service.npu_bridge import validate_result
        out=validate_result(request(CORE/'runtime/service.sock','POST','/v1/classify',{'model':'ryzenai-quicktest-10class','input':[0.0]*3072},timeout=15))
        self.event('npu_classified',cycle=cycle,result=out,application_accuracy_verified=False)
    def reconcile_original_stop(self):
        if not self.stop_intent or self.restore_started:return
        def terminal():
            state=command('systemctl','--user','show','aceis-inference.service','-p','ActiveState','--value')
            return state if state not in {'deactivating','activating','reloading'} else None
        state=wait_until(terminal,65,'original stop-state reconciliation')
        if state in {'inactive','failed'}:
            if command('systemctl','--user','show','aceis-inference.service','-p','MainPID','--value')!='0':raise ServiceError('inactive original still has MainPID')
            self.router_stopped=True
        elif state=='active':
            h=health(ROUTER_SOCKET)
            if h['status']!='ready' or h['fault'] is not None or not h['gpu']['flash_resident'] or h['gpu']['ollama_selected']!='coder-next':raise ServiceError('original active state is not a confirmed unchanged baseline')
            self.router_stopped=False;self.stop_intent=False
        else:raise ServiceError('original stop outcome is unknown: '+str(state))
    def restore(self):
        production_hashes()
        if self.router_stopped:
            if not self.restore_started:
                # Only after fixed candidate stop and physical release.
                physical_idle();self.event('production_start_requested');self.restore_started=True
                # A start timeout is reconciled through health, never replayed.
                try:command('systemctl','--user','start','aceis-inference.service',timeout=30)
                except (subprocess.TimeoutExpired,subprocess.CalledProcessError):pass
            wait_until(lambda:health(ROUTER_SOCKET),180,'original Router ready')
            if self.restore_job is None:
                if self.restore_submission_requested:raise ServiceError('original warm-restore submission uncertain; no automatic replay')
                body={'model':'coder-next','messages':[{'role':'user','content':'Reply with OK.'}],'max_tokens':1,'timeout_seconds':300}
                self.event('warm_restore_submit_requested')
                self.restore_submission_requested=True;self.restore_deadline=time.monotonic()+305
                out=request(ROUTER_SOCKET,'POST','/v1/jobs',body);jid=out.get('id')
                if not isinstance(jid,str) or len(jid)!=32:raise ServiceError('original warm-restore submission uncertain; not replayed')
                self.restore_job=jid;self.event('warm_restore_job_identified',job_id=jid)
            def done():
                r=request(ROUTER_SOCKET,'GET','/v1/jobs/'+self.restore_job);return r if r.get('status') in {'completed','failed','cancelled'} else None
            result=wait_until(done,max(.01,self.restore_deadline-time.monotonic()),'original coder-next warm restore')
            if result['status']!='completed':raise ServiceError('original coder-next warm restore failed; not replayed')
            h=health(ROUTER_SOCKET)
            if h['status']!='ready' or h['fault'] is not None or h['active'] is not None or h['queue_depth']!=0 or h['gpu']['ollama_selected']!='coder-next' or not h['gpu']['flash_resident']:raise ServiceError('original warm baseline not restored')
            provider_after=json.loads(docker('inspect',ORIGINAL_PROVIDER))[0]
            if provider_after['Image']!=self.original_provider['Image'] or provider_after['Mounts']!=self.original_provider['Mounts'] or not provider_after['State']['Running']:raise ServiceError('original provider not restored unchanged')
            hashes=production_hashes();self.router_stopped=False;self.stop_intent=False
            self.event('production_restored',health=h,hashes=hashes,original_provider_id=ORIGINAL_PROVIDER)
        self.restore_scheduler()
    def restore_scheduler(self):
        if not self.pause_intent or self.original_scheduler_paused is not False:return
        h=health(ROUTER_SOCKET)
        if h['status']!='ready' or h['fault'] is not None:raise ServiceError('do not resume scheduler over unconfirmed original readiness')
        status=orch('status')
        if status['paused']:
            try:orch('resume_scheduler')
            except Exception:
                # Reconcile a committed resume, never blindly replay.
                status=orch('status')
                if status['paused']:raise
            status=orch('status')
            if status['paused']:raise ServiceError('scheduler resume unconfirmed')
        self.paused_by_us=False;self.pause_intent=False
        self.event('scheduler_restored',status=status)
    def execute(self):
        self.event('preflight_started'); production_hashes();self.original=health(ROUTER_SOCKET)
        self.original_provider=json.loads(docker('inspect',ORIGINAL_PROVIDER))[0]
        if self.original_provider['Image']!=IMAGE or self.original_provider['Name']!='/aceis-inference-ollama-20261107' or self.original_provider['Config']['Labels'].get('aceis.inference.owner')!='/home/y-ooya/.local/state/aceis-inference' or not self.original_provider['State']['Running']:raise ServiceError('original provider identity changed')
        write(EVID/'original-provider-before.json',{k:self.original_provider[k] for k in ['Id','Image','Name','State','Mounts']})
        if self.original['status']!='ready' or self.original['fault'] is not None or self.original['active'] is not None or self.original['queue_depth'] or self.original['gpu']['ollama_selected']!='coder-next' or not self.original['gpu']['flash_resident']:raise ServiceError('original baseline is not the approved ready/quiescent state')
        npu=health(NPU_DIR+'/service.sock')
        if npu['status']!='ready':raise ServiceError('existing NPU agent not ready')
        net=json.loads(docker('network','inspect',NETWORK))[0]
        if not net.get('Internal') or net['Driver']!='bridge':raise ServiceError('existing internal runtime bridge unavailable')
        for name in [NAME_CORE,NAME_PROVIDER]:
            if docker('ps','-aq','--filter','name=^/'+name+'$'):raise ServiceError('owned test name exists; reconcile instead of replay')
        manifests=recheck_manifests(self.catalog);write(EVID/'manifest-recheck.json',manifests)
        if self.resume:
            resume_before,resume_registry=completed_download_resume(self.catalog,manifests)
            write(EVID/'validated-resume-store.json',resume_before)
            self.event('completed_downloads_reconciled',download_replay_allowed=False,registry_sha256=resume_registry)
        else:
            for d in [PROVIDER/'store',RUN/'registry']:
                if any(d.iterdir()):raise ServiceError('fresh acceptance requires empty dedicated model store and registry; do not replay')
        # Build/prove source before any service outage.
        build=subprocess.run(['python3','-B',str(SOURCE/'inference/core_container/build.py'),'--base',BASE,'--tag',TAG],capture_output=True,text=True,timeout=180)
        (EVID/'candidate-build.log').write_text(build.stdout+build.stderr)
        if build.returncode:raise ServiceError('candidate build failed before disruption')
        self.image=json.loads(docker('image','inspect',TAG))[0]['Id'];self.event('candidate_built',image=self.image)
        from inference.aceis_service.core_server import load_config
        self.configure_core();load_config(CORE/'config.json');OwnedCoreStop(self.policy)
        o=orch('status')
        if o.get('active_tasks') or o.get('blocked') or o.get('pending_recovery'):raise ServiceError('orchestrator not quiescent; no task interruption')
        self.original_scheduler_paused=o['paused']
        if not o['paused']:
            self.pause_intent=True;self.event('scheduler_pause_requested',original_paused=False)
            try:orch('pause')
            finally:
                paused=orch('status');self.paused_by_us=bool(paused['paused'])
        paused=orch('status')
        if not paused['paused'] or paused.get('active_tasks') or paused.get('blocked') or paused.get('pending_recovery'):raise ServiceError('scheduler pause/quiescence unconfirmed; no Router stop')
        current=health(ROUTER_SOCKET)
        if current['active'] is not None or current['queue_depth'] or current['fault'] is not None or current['gpu']['ollama_selected']!='coder-next' or not current['gpu']['flash_resident']:raise ServiceError('Router acquired work or baseline changed; no stop')
        self.stop_intent=True;self.event('router_stop_requested',original_health=current,orchestrator=o)
        try:
            command('systemctl','--user','stop','aceis-inference.service',timeout=65)
        finally:
            state=command('systemctl','--user','show','aceis-inference.service','-p','ActiveState','--value')
            self.router_stopped=state in {'inactive','failed'}
        if not self.router_stopped:raise ServiceError('original Router stop unconfirmed')
        if json.loads(docker('inspect',ORIGINAL_PROVIDER))[0]['State']['Running']:raise ServiceError('original owned Ollama stop unconfirmed')
        self.baseline=physical_idle();self.event('host_released',resources=self.baseline,npu=health(NPU_DIR+'/service.sock'))
        thread=threading.Thread(target=self.monitor,daemon=True);thread.start()
        if not self.monitor_ready.wait(5):raise RuntimeError('resource monitor startup unconfirmed')
        self.check()
        if self.resume:
            before,registry_before=resume_before,resume_registry
            self.event('resume_without_download',store_bytes=before['total_bytes'],pull_calls=0,registry_unchanged=True)
        else:
            self.create_provider('bridge');self.start_provider();self.event('download_engine_ready',container_id=self.provider,initial_inventory=self.adapter('GET','/api/tags'))
            fixed=self.adapter; parent=self
            class Audit:
                identity=fixed.identity
                def __call__(self,method,path,body=None):
                    parent.check();parent.event('model_management_request',method=method,path=path,model=(body or {}).get('model'))
                    out=fixed(method,path,body);parent.check();return out
            manager=ModelManager(RUN/'registry',self.catalog,OllamaAdapter(Audit()),HISTORICAL,PROVIDER/'store')
            for item in self.catalog:
                # Repeat tag metadata immediately before each non-replayed pull.
                recheck_manifests([item]);start=time.monotonic();out=manager.install(item['id']);self.event('model_installed',model=item['id'],seconds=time.monotonic()-start,record=out)
            self.stop_provider();before=store_snapshot(manifests);write(EVID/'store-before-recreate.json',before)
            registry_before=digest(RUN/'registry/models.json');self.event('download_phase_complete',store_bytes=before['total_bytes'],registry_sha256=registry_before)
            self.remove_provider()
        # All later providers have only Internal=true network and cannot pull.
        for cycle in [1,2]:
            self.create_provider(NETWORK);self.start_runtime(cycle)
            inspected=ModelManager(RUN/'registry',self.catalog,OllamaAdapter(self.adapter),HISTORICAL,PROVIDER/'store')
            for item in self.catalog:
                observation=inspected.inspect(item['id'])
                if not observation['managed'] or not observation['digest_matches']:raise ServiceError('persisted managed model identity not retained')
                self.event('persisted_model_observed',cycle=cycle,model=item['id'],observation=observation)
                self.inference(item,cycle)
            self.classify(cycle);self.stop_runtime(cycle);self.remove_provider()
            after=store_snapshot(manifests);write(EVID/('store-after-cycle'+str(cycle)+'.json'),after)
            if after!=before or digest(RUN/'registry/models.json')!=registry_before:raise ServiceError('persistent store/registry bytes or file identity changed')
            self.event('persistent_volume_verified',cycle=cycle,store_bytes=after['total_bytes'],all_hashes_and_inodes_unchanged=True,registry_unchanged=True)
        self.monitor_stop.set();self.restore();self.event('acceptance_complete',scope='Two explicit small acceptance models; not production target completion',result='PASS_SMALL_MODEL_CONTAINER_PERSISTENCE_ACCEPTANCE')
    def reconcile_candidate_creates(self):
        if self.core_create_pending:
            found=OwnedCoreStop(self.policy).inspect()
            if found:self.core=found[1]['Id']
            self.core_create_pending=False
        if self.provider_create_pending is not None:
            network=self.provider_create_pending
            found=docker('ps','-aq','--no-trunc','--filter','name=^/'+NAME_PROVIDER+'$')
            if found:
                candidate=self.adapter_for(found,network);candidate.inspect()
                self.provider=found;self.adapter=candidate
            self.provider_create_pending=None
    def cleanup(self):
        self.in_cleanup=True;self.monitor_stop.set();self.reconcile_candidate_creates()
        if self.core or self.sup:self.stop_runtime('cleanup')
        if self.provider:self.remove_provider()
        self.reconcile_original_stop()
        if self.router_stopped:self.restore()
        else:self.restore_scheduler()


def main():
    global EVID
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--resume-after-download',action='store_true');args=p.parse_args()
    if args.resume_after_download:EVID=RUN/'evidence-resume-after-download'
    original=read_catalog(ROOT/'provenance-research/acceptance-catalog.json')
    catalog=[dict(item,id=item['id'].replace('acceptance-','test-',1)) for item in original]
    if not args.execute:
        print(json.dumps({'action':'PLAN_ONLY','models':[{'id':x['id'],'reference':x['reference'],'license':x['license'],'digest':x['digest']} for x in catalog],'production_targets_completed':False,'will_stop_temporarily':['aceis-inference.service'],'will_preserve':['aceis-npu.service','production source/settings/models'],'containers':[NAME_PROVIDER,NAME_CORE],'model_store':str(PROVIDER/'store'),'client_transport':'owner-only UDS across container boundary','backend_transport':'private internal Docker HTTP','runtime_recreations':2},indent=2));return 0
    private(RUN)
    for path in [EVID,PROVIDER,WEIGHTS,HOST,CORE,RUN/'registry']:private(path)
    for path in [PROVIDER/'store',PROVIDER/'input',HOST/'state',HOST/'runtime',CORE/'state',CORE/'runtime']:private(path)
    if (EVID/'journal.json').exists():raise ServiceError('prior acceptance journal exists; inspect instead of replay')
    if not args.resume_after_download:write(RUN/'catalog.json',catalog)
    elif read_catalog(RUN/'catalog.json')!=catalog:raise ServiceError('resume catalog changed')
    run=Run(catalog,resume=args.resume_after_download)
    # No asynchronous Python exception is injected into an uncertain model pull.
    # Signals request interruption through check(), then normal scoped cleanup.
    def interrupt(*_):run.fault='operator interruption requested'
    signal.signal(signal.SIGINT,interrupt);signal.signal(signal.SIGTERM,interrupt)
    try:run.execute();return 0
    except Exception as exc:
        try:run.event('acceptance_failed',error=type(exc).__name__+': '+str(exc),automatic_retry=False)
        except Exception:pass
        try:run.cleanup()
        except Exception as cleanup:
            try:run.event('SAFETY_HOLD',error=str(cleanup),production_restart_deferred=True)
            except Exception:pass
            # Retain ownership descriptors if physical/provider stop is unknown.
            # Parent must report this exact blocker; no broad kill/reset occurs.
            while True:time.sleep(60)
        return 1

if __name__=='__main__':raise SystemExit(main())
