"""Default-profile target acceptance using exact existing assets/provider.

Historical EVO-X3 harness: SOURCE below points to an older frozen snapshot.
This module does not accept this integrated checkout as its runtime source.
Do not execute it as current-tree acceptance without a separately reviewed adapter.

Plan-only by default. No model download, import, provider create/remove,
production source/settings change, repack or broad authority is implemented.
"""
from __future__ import annotations
import argparse,datetime,fcntl,hashlib,http.client,json,os,pathlib,signal,stat,subprocess,threading,time
from inference.acceptance_container import run as shared
from inference.aceis_service.backends import Backends,IMAGE
from inference.aceis_service.lifecycle_host import OwnedOllama
from inference.aceis_service.host_supervisor import HostSupervisor,OwnedCoreStop
from inference.aceis_service.core import ServiceError,snapshot,check_resources
from inference.aceis_service.core_server import load_config

ROOT=pathlib.Path('/home/y-ooya/laf-target-acceptance-20261108');SOURCE=ROOT/'source';RUN=ROOT/'runtime';EVID=RUN/'evidence'
NAME='laf-core-targets-20261108';OWNER=str(RUN);NETWORK=shared.NETWORK;ORIGINAL=shared.ORIGINAL_PROVIDER
PROD=pathlib.Path('/home/y-ooya/.local/state/aceis-inference');CFG=PROD/'config.json'
TAG='laf-core-local:targets-20261108';FROZEN=pathlib.Path('/home/y-ooya/laf-runtime-audit-20261108/fixture-proposal')
EXPECTED={'aceis-coder-next:latest':'d2e9ab6c7c8101b1a7caa8e1f7baf5627ecf24debf219c576d0939f4fa35eaec','aceis-gpt-oss-120b:latest':'ed99e8f2d9bfd1b094f7f06ccfe932f1e2b40e41d5c5a9e8eab294212c54a896'}
write,docker,utc,health,request,command,orch,wait_until,physical_idle=shared.write,shared.docker,shared.utc,shared.health,shared.request,shared.command,shared.orch,shared.wait_until,shared.physical_idle

FIXTURE_SHA={'core-config.json':'a23b68e480fa41df45b8c646af5dd889ba5dafcb2a65d7021b3772c7f2a5296f','host-config.json':'3d41a2dd58559a8ab85d6b9ddab92850cad5a0d5c4ce09f39191e757b6b6721b','code-config-package-sha256.json':'85e729484252c5c2e09e66945670e14afca62e953aba0ad889984cc6fdd55050'}
PAYLOAD_AUDIT_SHA='7516f8e3faf0bb4bd88d25f06e386e6027ecef89e176612ccfe89cf2bbb5b961'
SOURCE_MAP_SHA='20bd34d3e9fee6e2383d93ade34c4f705b32be74971089678c3d4d11ab691d99'
ASSET_ROOT=pathlib.Path('/home/y-ooya/workspace/project-kiss-infra/.cache/backend-evaluation/strata-v027-e0152')
PACK_ROOT=pathlib.Path('/home/y-ooya/workspace/project-kiss-infra/agents/local_llm/.runtime/backend-trials/strata-20261030T081056Z-f9f0d1b0/full')
ENGINE_FILES_SHA='8e87d1230c5bb2d47295cd485f75eecf9225645a5a6992d40df70ea85d242c57'
ENGINE_COMPONENT_SHA='abd7ecedc07f5dddc1d4f5bd5e5ac0f4912bf279cd6becef4306c5b5d7fad2fa'
LOCAL_VERIFICATION_SHA='6a78dd6ee1a941b251442c7504faf090ba3d5cea3312f072718d64b354ad63d1'
SOURCE_MANIFESTS=[('strata-source-files.json','b34d9d527d6a7dfa8d3c7b07b288223dd9c32ba0773fcdd0cc3755b4770604da','strata-source'),('gguf-source-files.json','c741a3edc069bcd8c36e63c7de0f0700a0757067366e59034e459066c46b0233','llama-source')]
WEIGHT_SHA_BYTES={
 '6bcfc9f9c37901eeb92172e2ab871224dab36a453d263bcb2547f737409534da':15524827040,
 '817def0691ee9d08bf3dc4444be7aed29c9e52091e8fa9d97901ce7e7f6f01d3':14872168352,
 '23aa634d47dca9b4ca3ea249384e6f01951b24c83cdc076f37f6f43d6c99883f':14503294496,
 '249c768cc5f130dc731567d6edcbdacc48e14dec9e02c5dbe2b2185d2c5bdb2b':3510702144,
 '582bd40f6886200101f4c4ed9f25f3fe80cc14c86e9e2b37746cd8904a0c622d':63387346208}
FLASH_FILES={'Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf':('69820c02ec7d0b45ef2ebb19d6620299db749fe2aded7f39f93c6b88b199b720',37623740192),'Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf':('316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113',28800138432)}
PRIOR_TARGET_JOURNAL_SHA='31b7db48a41d6730263c5fd016c0ed23b95bfeaffdce58c45bae5d34ab032903'
PACK_FILES={'manifest.json','index.txt','experts.bin','embd.bin','dense.bin','experts.json','tokenizer/chat_template.jinja'}


def pinned_json(path,expected):
    if path.is_symlink() or shared.digest(path)!=expected:raise ServiceError('pinned acceptance evidence/config changed: '+str(path))
    return json.loads(path.read_text())

def fixture_identity():
    return {name:shared.digest(FROZEN/name) for name,sha in FIXTURE_SHA.items() if pinned_json(FROZEN/name,sha) is not None}


def payload_identity():
    path=ROOT/'verification/current-payload-sha256.json';value=pinned_json(path,PAYLOAD_AUDIT_SHA)
    expected={str(PROD/'store/blobs'/('sha256-'+sha)):(sha,n) for sha,n in WEIGHT_SHA_BYTES.items()}
    flashroot=pathlib.Path('/home/y-ooya/workspace/project-kiss-infra/models/large-coder-b3/qwen38-flash-next')
    expected.update({str(flashroot/name):data for name,data in FLASH_FILES.items()})
    expected.update({str(PACK_ROOT/name):(None,None) for name in PACK_FILES})
    paths=[x.get('path') for x in value.get('entries',[])]
    if value.get('completed') is not True or len(paths)!=len(expected) or len(set(paths))!=len(paths) or set(paths)!=set(expected):raise ServiceError('exact unique approved14-file payload set required')
    for row in value['entries']:
        wanted,n=expected[row['path']]
        if row['expected_sha256']!=wanted or wanted is not None and (row['expected_bytes']!=n or row['actual_sha256']!=wanted):raise ServiceError('target upstream payload metadata mismatch')
        p=pathlib.Path(row['path']);st=p.lstat()
        if not stat.S_ISREG(st.st_mode) or p.is_symlink() or (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)!=(row['dev'],row['inode'],row['read_bytes'],row['mtime_ns']):raise ServiceError('audited target asset changed; no runtime')
    return {'audit_sha256':PAYLOAD_AUDIT_SHA,'files':[{k:x[k] for k in ['path','dev','inode','mtime_ns','read_bytes','actual_sha256']} for x in value['entries']]}

def manifest_identity():
    root=PROD/'store';out={}
    for name,dig in EXPECTED.items():
        model,tag=name.split(':',1);alias=root/'manifests-v2/ollama.com/library'/model/tag
        info=alias.lstat();target='../../../../blobs/sha256-'+dig
        if not stat.S_ISLNK(info.st_mode) or info.st_uid!=os.getuid() or os.readlink(alias)!=target:raise ServiceError('prepared target manifest alias changed')
        p=root/'blobs'/('sha256-'+dig)
        if p.is_symlink() or shared.digest(p)!=dig:raise ServiceError('prepared target manifest digest changed')
        out[name]={'digest':dig,'alias_inode':info.st_ino,'alias_dev':info.st_dev,'alias_mtime_ns':info.st_mtime_ns,'target':target,'blob_inode':p.stat().st_ino,'blob_dev':p.stat().st_dev}
    return out


def runtime_implementation_identity():
    fixtures=fixture_identity();frozen=pinned_json(FROZEN/'code-config-package-sha256.json',FIXTURE_SHA['code-config-package-sha256.json']);rows={}
    for path,expected in frozen.items():
        if not path.startswith(str(ASSET_ROOT)+'/'):continue
        actual=shared.digest(path)
        if actual!=expected:raise ServiceError('frozen runtime implementation/package changed: '+path)
        rows[path]=actual
    if not rows:raise ServiceError('frozen runtime implementation map absent')
    records=ROOT/'provenance-flash';pinned_json(records/'local-verification.json',LOCAL_VERIFICATION_SHA)
    engine_files=pinned_json(records/'engine-file-verification.json',ENGINE_FILES_SHA);engine=ASSET_ROOT/'engine-bundle';engine_rows={}
    expected_engine={x['path'] for x in engine_files}|{'engine-component.json'}
    actual_engine={str(p.relative_to(engine)) for p in engine.rglob('*') if p.is_file() or p.is_symlink()}
    if len(engine_files)!=279 or actual_engine!=expected_engine:raise ServiceError('engine artifact set changed')
    if (engine/'engine-component.json').is_symlink() or shared.digest(engine/'engine-component.json')!=ENGINE_COMPONENT_SHA:raise ServiceError('signed engine manifest changed')
    for x in engine_files:
        p=engine/x['path']
        if p.is_symlink() or p.stat().st_size!=x['bytes'] or shared.digest(p)!=x['sha256']:raise ServiceError('signed engine artifact changed: '+x['path'])
        engine_rows[x['path']]=x['sha256']
    source_rows={}
    for name,expected,folder in SOURCE_MANIFESTS:
        record=pathlib.Path('/home/y-ooya/workspace/project-kiss-infra/inference/backend-evaluation/host_trial')/name;data=pinned_json(record,expected);base=ASSET_ROOT/folder
        scope=base if folder=='strata-source' else base/'gguf-py'
        actual_paths={str(p.relative_to(base)) for p in scope.rglob('*.py') if p.is_file() or p.is_symlink()}
        if actual_paths!={x['path'] for x in data['files']}:raise ServiceError('verified Python path set changed')
        for x in data['files']:
            p=base/x['path']
            if p.is_symlink() or not p.is_file():raise ServiceError('invalid verified Python file')
            blob=p.read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
            if p.is_symlink() or len(blob)!=x['bytes'] or actual!=x['git_blob_sha1']:raise ServiceError('verified Python source changed: '+x['path'])
            source_rows[folder+'/'+x['path']]=actual
    original=pinned_json(ROOT/'verification/initial-source-hashes.json',SOURCE_MAP_SHA)
    for path,expected in original.items():
        if shared.digest(SOURCE/path)!=expected:raise ServiceError('reviewed copied Core/control source changed: '+path)
    return {'fixture_sha256':fixtures,'frozen_runtime_files':rows,'signed_engine_files':engine_rows,'official_python_sources':source_rows,'copied_source_files':original}


def validate_layout_resume():
    prior=ROOT/'runtime/evidence';rows=pinned_json(prior/'journal.json',PRIOR_TARGET_JOURNAL_SHA)
    if not rows or rows[-1].get('stage')!='scheduler_restored' or not any(x.get('stage')=='production_restored' for x in rows):raise ServiceError('prior target restoration not confirmed')
    if any(x.get('stage') in {'runtime_ready','job_submitted','inference_completed'} for x in rows):raise ServiceError('prior target job outcome exists; no replay')
    failed=[x for x in rows if x.get('stage')=='acceptance_failed']
    if len(failed)!=1 or failed[0].get('error')!='RuntimeError: target Core exited before readiness':raise ServiceError('unsupported target failure; reconcile explicitly')
    removed=[x for x in rows if x.get('stage')=='core_removed']
    if len(removed)!=1:raise ServiceError('prior owned Core cleanup not confirmed')
    cid=removed[0]['container_id'];state=json.loads((prior/('core-'+cid[:12]+'-state.json')).read_text());log=(prior/('core-'+cid[:12]+'.log')).read_text()
    if state.get('Running') or state.get('OOMKilled') or state.get('ExitCode')!=1 or 'but it was opened as a whole model' not in log:raise ServiceError('prior failure is not the confirmed shard-layout error')
    return {'prior_journal_sha256':PRIOR_TARGET_JOURNAL_SHA,'prior_core_removed':cid,'prior_job_submissions':0,'source_verified_layout_fix':True}


class FixedExistingOllama(OwnedOllama):
    """No name-based discovery or create fallback, ever; only existing full ID."""
    cid=ORIGINAL
    def __init__(self,config,config_path):
        super().__init__(config,config_path);self.backend.cid=ORIGINAL
    def _reconcile(self):self.inspect()
    def inspect(self):
        if self.backend.cid!=ORIGINAL:raise ServiceError('existing provider ID changed')
        info=self.backend.inspect_owned();h=info['HostConfig']
        devices=[{'PathOnHost':p,'PathInContainer':p,'CgroupPermissions':'rwm'} for p in ['/dev/kfd','/dev/dri/renderD128']]
        if info['Id']!=ORIGINAL or info['Name']!='/aceis-inference-ollama-20261107' or h.get('GroupAdd')!=['990'] or h.get('Devices')!=devices or h.get('SecurityOpt')!=['no-new-privileges:true'] or h.get('NanoCpus')!=8*10**9 or h.get('PidsLimit')!=512:raise ServiceError('fixed production provider identity/security mismatch')
        return info
    def running(self):return self.inspect()['State']['Running']
    def ensure(self,check):
        self.inspect();manifest_identity();check()
        # cid is pinned before start_ollama, so its creation branch is unreachable.
        self.backend.start_ollama(check);self.inspect()
        self.inventory('/api/tags')
    def inventory(self,path):
        if path not in {'/api/tags','/api/ps','/api/version'}:raise ServiceError('read-only fixed provider inventory route required')
        info=self.inspect()
        if not info['State']['Running']:raise ServiceError('existing provider stopped')
        self.backend.address=info['NetworkSettings']['Networks'][NETWORK]['IPAddress']
        value=self.backend.api(path)
        if path=='/api/tags':
            observed={x['name']:x['digest'].removeprefix('sha256:') for x in value['models']}
            if any(observed.get(k)!=v for k,v in EXPECTED.items()):raise ServiceError('prepared engine target manifest changed')
        return value
    def stop(self):
        self.inspect()
        # Accepted adapter stops only its already-pinned ID, then absolute barrier.
        super().stop();self.inspect()


class GracefulCoreStop(OwnedCoreStop):
    def stop(self):
        found=self.inspect()
        if found is None:return
        cid,info=found
        if info['State']['Running']:self.cli('stop','-t','15',cid,timeout=25)
        info=json.loads(self.cli('inspect',cid))[0];self.validate(info)
        if info['State']['Running']:raise ServiceError('target Core stop unconfirmed')


class TargetRun(shared.Run):
    def __init__(self):
        super().__init__([]);self.reused=None;self.manifests_before=None;self.payload_before=None
    def event(self,stage,**values):
        value={'utc':utc(),'stage':stage,**values};self.events.append(value)
        try:write(EVID/'journal.json',self.events);print(json.dumps(value,ensure_ascii=False),flush=True)
        except (OSError,ValueError) as exc:
            self.diagnostic_errors.append('journal/output: '+str(exc))
            if not self.in_cleanup:raise
    def monitor(self):
        try:
            with open(EVID/'resources.jsonl','a') as f:
                os.chmod(EVID/'resources.jsonl',0o600);self.monitor_ready.set()
                while not self.monitor_stop.wait(1):
                    s=snapshot();f.write(json.dumps({'utc':utc(),**s})+'\n');f.flush()
                    if self.baseline:check_resources(s,self.baseline)
        except Exception as exc:
            self.fault=type(exc).__name__+': '+str(exc);self.monitor_ready.set()
            if self.sup is None and self.reused is not None and self.router_stopped and not self.restore_started:
                try:self.reused.stop()
                except Exception:pass
    def create_provider(self,*a,**kw):raise ServiceError('provider creation forbidden for existing target reuse')
    def remove_provider(self,*a,**kw):raise ServiceError('production provider removal forbidden')
    def configure_core(self):
        fixture_identity();config=pinned_json(FROZEN/'core-config.json',FIXTURE_SHA['core-config.json']);config['npu_socket']='/npu-agent/service.sock'
        names=list(FLASH_FILES)
        model_dest={'/assets/model/native.gguf':'/assets/model/'+names[0],'/assets/model/ple.gguf':'/assets/model/'+names[1]}
        for flag,old in [('--native','/assets/model/native.gguf'),('--ple-gguf','/assets/model/ple.gguf')]:
            at=config['strata_command'].index(flag)+1
            if config['strata_command'][at]!=old:raise ServiceError('unexpected frozen model command')
            config['strata_command'][at]=model_dest[old]
        write(RUN/'core-config.json',config)
        original=pinned_json(FROZEN/'host-config.json',FIXTURE_SHA['host-config.json']);mounts=[]
        paths={'/host-lifecycle':RUN/'host-runtime','/core-state':RUN/'core-state','/core-runtime':RUN/'core-runtime','/tmp':RUN/'tmp','/config/core.json':RUN/'core-config.json'}
        for m in original['core']['mounts']:
            replacement=model_dest.get(m['Destination'],m['Destination'])
            if m['Destination'] in model_dest and (pathlib.Path(m['Source']).name!=pathlib.Path(replacement).name or m['RW']):raise ServiceError('exact read-only original shard basename required')
            mounts.append({**m,'Source':str(paths.get(m['Destination'],m['Source'])),'Destination':replacement})
        mounts.append({'Source':shared.NPU_DIR,'Destination':'/npu-agent','RW':False})
        expected_rw={'/core-state','/core-runtime','/tmp'}
        expected_ro={'/assets/engine','/assets/source','/deps/regex','/deps/jinja2','/deps/markupsafe','/assets/pack',*model_dest.values(),'/host-lifecycle','/config/core.json','/npu-agent'}
        if len(mounts)!=14 or {x['Destination'] for x in mounts if x['RW']}!=expected_rw or {x['Destination'] for x in mounts if not x['RW']}!=expected_ro:raise ServiceError('exact frozen target mount permissions required')
        self.policy={**original['core'],'container_name':NAME,'image':self.image,'owner':OWNER,'mounts':mounts}
        h={'state_dir':str(RUN/'host-state'),'runtime_dir':str(RUN/'host-runtime'),'generation_lock':str(shared.HISTORICAL),'lease_seconds':30,'ollama':original['ollama'],'core':self.policy}
        write(RUN/'host-config.json',h);load_config(RUN/'core-config.json');GracefulCoreStop(self.policy);return h
    def create_core(self):
        if docker('ps','-aq','--filter','name=^/'+NAME+'$'):raise ServiceError('target Core name exists; reconcile instead of adoption')
        args=['create','--pull=never','--name',NAME,'--label','aceis.core.owner='+OWNER,'--network',NETWORK,'--user','1000:1000','--group-add','990','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--ipc','private','--memory','40g','--memory-swap','40g','--cpus','16','--pids-limit','512','--restart','no','--env','PYTHONPATH=/deps','--env','HOME=/tmp','--env','TMPDIR=/tmp','--log-opt','max-size=10m','--log-opt','max-file=2']
        for p in ['/dev/kfd','/dev/dri/renderD128']:args+=['--device',p+':'+p+':rwm']
        for m in self.policy['mounts']:args+=['--mount',f"type=bind,source={m['Source']},target={m['Destination']}"+(',readonly' if not m['RW'] else '')]
        self.core_create_pending=True;self.event('core_create_requested',name=NAME)
        try:cid=docker(*args,self.image,'--config','/config/core.json')
        except Exception:
            found=GracefulCoreStop(self.policy).inspect()
            if found:self.core=found[1]['Id'];self.core_create_pending=False;self.event('core_create_outcome_reconciled',container_id=self.core)
            raise
        self.core=cid;info=GracefulCoreStop(self.policy).inspect()[1]
        if info['HostConfig'].get('GroupAdd')!=['990'] or info['HostConfig'].get('SecurityOpt')!=['no-new-privileges:true']:raise ServiceError('unexpected target Core groups/security')
        self.core_create_pending=False;write(EVID/('core-'+cid[:12]+'-inspect.json'),info)
    def reconcile_candidate_creates(self):
        if self.provider is not None or self.provider_create_pending is not None:raise ServiceError('invalid provider creation/removal state for target reuse')
        if self.core_create_pending:
            found=GracefulCoreStop(self.policy).inspect()
            if found:self.core=found[1]['Id']
            self.core_create_pending=False
    def start_runtime(self,cycle):
        config=self.configure_core();self.create_core()
        self.sup=HostSupervisor(config,RUN/'host-config.json',ollama_factory=FixedExistingOllama,core_factory=GracefulCoreStop);self.sup.start();docker('start',self.core)
        def ready():
            self.check();info=GracefulCoreStop(self.policy).inspect()[1]
            if not info['State']['Running']:raise RuntimeError('target Core exited before readiness')
            h=health(RUN/'core-runtime/service.sock');return h if h['status']=='ready' and h['fault'] is None else None
        h=wait_until(ready,150,'target default Core readiness');self.event('runtime_ready',cycle=cycle,health=h,inventory=self.reused.inventory('/api/tags'))
    def stop_provider(self):
        if self.reused is not None:self.reused.stop()
    def stop_runtime(self,cycle):
        oom=False
        if self.core:
            GracefulCoreStop(self.policy).stop();info=GracefulCoreStop(self.policy).inspect()[1];cid=self.core;oom=bool(info['State'].get('OOMKilled'))
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
        if oom and not self.in_cleanup:raise ServiceError('target Core OOM; scoped safety cleanup completed')
    def inference(self,model,cycle):
        self.check();manifest_identity();start=time.monotonic()
        tokens,timeout=(8,30) if model=='flash' else ((16,300) if model=='coder-next' else (128,300))
        body={'model':model,'messages':[{'role':'user','content':'Reply with OK.'}],'max_tokens':tokens,'timeout_seconds':timeout}
        out=request(RUN/'core-runtime/service.sock','POST','/v1/jobs',body);jid=out.get('id')
        if not isinstance(jid,str) or len(jid)!=32:raise ServiceError('target submission uncertain; never replayed')
        self.event('job_submitted',cycle=cycle,model=model,job_id=jid,max_tokens=tokens,timeout_seconds=timeout)
        def terminal():
            self.check();x=request(RUN/'core-runtime/service.sock','GET','/v1/jobs/'+jid)
            if x.get('id')!=jid or x.get('model')!=model:raise RuntimeError('target job identity changed')
            return x if x.get('status') in {'completed','failed','cancelled'} else None
        result=wait_until(terminal,timeout+5,'target inference')
        if result['status']!='completed' or not result.get('result',{}).get('content','').strip():raise ServiceError('target inference failed or empty final content: '+str(result)[:500])
        ps=self.reused.inventory('/api/ps');h=health(RUN/'core-runtime/service.sock')
        if not h['gpu']['flash_resident']:raise ServiceError('Flash residency lost')
        if model=='flash':
            if ps['models']:raise ServiceError('unexpected large model on initial Flash-only request')
        else:
            ref='aceis-'+model+':latest'
            if len(ps['models'])!=1 or ps['models'][0]['name']!=ref or ps['models'][0]['digest'].removeprefix('sha256:')!=EXPECTED[ref] or ps['models'][0].get('size_vram',0)<=0:raise ServiceError('target GPU/manifest/single-model identity unconfirmed')
        self.event('inference_completed',cycle=cycle,model=model,seconds=time.monotonic()-start,result=result,engine_ps=ps,health=h)
    def classify(self,cycle):
        from inference.aceis_service.npu_bridge import validate_result
        out=validate_result(request(RUN/'core-runtime/service.sock','POST','/v1/classify',{'model':'ryzenai-quicktest-10class','input':[0.0]*3072},timeout=15))
        self.event('npu_classified',cycle=cycle,result=out,application_accuracy_verified=False)
    def execute(self):
        self.event('preflight_started',scope='existing verified target assets, private local/internal only; no distribution or new terms acceptance')
        shared.production_hashes();self.payload_before=payload_identity();self.manifests_before=manifest_identity();self.implementation_before=runtime_implementation_identity()
        write(EVID/'verified-runtime-implementation.json',self.implementation_before);write(EVID/'payload-before.json',self.payload_before);write(EVID/'manifest-before.json',self.manifests_before)
        prod_config=json.loads(CFG.read_text());self.reused=FixedExistingOllama(prod_config,CFG);self.original_provider=self.reused.inspect()
        if not self.original_provider['State']['Running']:raise ServiceError('original provider not running')
        self.original=health(shared.ROUTER_SOCKET)
        if self.original['status']!='ready' or self.original['fault'] is not None or self.original['active'] is not None or self.original['queue_depth'] or self.original['gpu']['ollama_selected']!='coder-next' or not self.original['gpu']['flash_resident']:raise ServiceError('original baseline changed; no disruption')
        self.event('prepared_targets_verified',tags=self.reused.inventory('/api/tags'),payload_audit=self.payload_before['audit_sha256'])
        if health(shared.NPU_DIR+'/service.sock')['status']!='ready':raise ServiceError('existing NPU agent not ready')
        if docker('ps','-aq','--filter','name=^/'+NAME+'$'):raise ServiceError('target Core name already exists')
        build=subprocess.run(['python3','-B',str(SOURCE/'inference/core_container/build.py'),'--base',shared.BASE,'--tag',TAG],capture_output=True,text=True,timeout=180)
        (EVID/'build.log').write_text(build.stdout+build.stderr)
        if build.returncode:raise ServiceError('target source-image build failed')
        self.image=json.loads(docker('image','inspect',TAG))[0]['Id'];self.configure_core();self.event('candidate_built',image=self.image)
        o=orch('status')
        if o.get('active_tasks') or o.get('blocked') or o.get('pending_recovery'):raise ServiceError('orchestrator not quiescent')
        self.original_scheduler_paused=o['paused']
        if not o['paused']:
            self.pause_intent=True;self.event('scheduler_pause_requested',original_paused=False)
            try:orch('pause')
            finally:self.paused_by_us=bool(orch('status')['paused'])
        paused=orch('status')
        if not paused['paused'] or paused.get('active_tasks') or paused.get('blocked') or paused.get('pending_recovery'):raise ServiceError('pause/quiescence not confirmed')
        h=health(shared.ROUTER_SOCKET)
        if h['status']!='ready' or h['fault'] is not None or h['active'] is not None or h['queue_depth'] or h['gpu']['ollama_selected']!='coder-next' or not h['gpu']['flash_resident']:raise ServiceError('Router acquired work or changed profile')
        self.stop_intent=True;self.event('router_stop_requested',health=h)
        try:command('systemctl','--user','stop','aceis-inference.service',timeout=65)
        finally:self.router_stopped=command('systemctl','--user','show','aceis-inference.service','-p','ActiveState','--value') in {'inactive','failed'}
        if not self.router_stopped or self.reused.running():raise ServiceError('original stop unconfirmed')
        self.baseline=physical_idle();self.event('host_released',resources=self.baseline)
        thread=threading.Thread(target=self.monitor,daemon=True);thread.start()
        if not self.monitor_ready.wait(5):raise RuntimeError('target resource monitor startup unconfirmed')
        self.check()
        for cycle in [1,2]:
            self.start_runtime(cycle)
            for model in ['flash','coder-next','gpt-oss-120b']:self.inference(model,cycle)
            self.classify(cycle);self.stop_runtime(cycle)
            after_payload=payload_identity();after_manifest=manifest_identity()
            if runtime_implementation_identity()!=self.implementation_before:raise ServiceError('runtime implementation changed during acceptance')
            write(EVID/('payload-after-cycle'+str(cycle)+'.json'),after_payload);write(EVID/('manifest-after-cycle'+str(cycle)+'.json'),after_manifest)
            if after_payload!=self.payload_before or after_manifest!=self.manifests_before:raise ServiceError('target model payload/manifest identity changed')
            self.event('existing_volume_reuse_verified',cycle=cycle,provider_id=ORIGINAL,payload_audit_sha256=after_payload['audit_sha256'],same_named_payload_inodes_mtimes_and_manifest_digests=True,download_calls=0,imports=0,copied_weight_bytes=0)
        self.monitor_stop.set();self.restore()
        self.event('acceptance_complete',result='PASS_DEFAULT_FLASH_NEXT_120B_CONTAINER_ACCEPTANCE_EXISTING_ASSETS',p0_complete=False,download_calls=0)


def main():
    global RUN,EVID,OWNER
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--resume-layout-fix',action='store_true');args=p.parse_args()
    resume=None
    if args.resume_layout_fix:
        resume=validate_layout_resume();RUN=ROOT/'runtime-layout-fix';EVID=RUN/'evidence';OWNER=str(RUN)
    if not args.execute:
        print(json.dumps({'action':'PLAN_ONLY','profiles':['flash','coder-next','gpt-oss-120b'],'core_mode':'unchanged default, including120B think=low','provider':'REUSE_EXACT_EXISTING_NO_CREATE_OR_REMOVE','container_id':ORIGINAL,'downloads':0,'copies':0,'core_memory_GiB':40,'provider_memory_GiB':32,'extra_swap':0,'devices':['/dev/kfd','/dev/dri/renderD128'],'network':NETWORK,'cycles':2,'original_restoration':'same unit/config/provider plus Flash/coder-next warm; NPU kept'},indent=2));return 0
    shared.private(RUN)
    for name in ['evidence','host-state','host-runtime','core-state','core-runtime','tmp']:shared.private(RUN/name)
    if (EVID/'journal.json').exists():raise ServiceError('prior target journal exists; inspect instead of replay')
    run=TargetRun()
    if resume:run.event('prior_layout_failure_reconciled',**resume)
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
            while True:time.sleep(60)
        return 1
if __name__=='__main__':raise SystemExit(main())
