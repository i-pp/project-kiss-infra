"""Finite human-host Strata measurement; never a daemon or generic command service."""
from contextlib import contextmanager
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import threading
import uuid

import assets
from owned_process import GIB, Limits, OwnedProcessRunner, system_probe

ACK='ACEIS_STRATA_FLASH_ACK'
MODEL='kiss-qwen3-coder-30b'
# Finite per-stage work, plus owned-stop time; whole work reserves120s for30B recovery.
STAGES={'imports':30,'pilot_build':300,'pilot_verify':180,'full_build':900,'full_verify':300,
        'index':30,'tokenizer':60,'encode':30,'decode':30}
WHOLE_SECONDS=2400
SOURCE_COMMIT=assets.COMMIT
INITIAL_FIXED_RUN='strata-20261030T061451Z-7ee17897'
PACK_HOOK_VERSION=1
RUN_STARTED=False


class Blocked(RuntimeError):pass


def require_initial_attempt_unconsumed(repo):
    prior=Path(repo)/'agents/local_llm/.runtime/backend-trials'/INITIAL_FIXED_RUN/'summary.json'
    if prior.exists() or prior.is_symlink():
        raise Blocked('PRIOR_ATTEMPT_EXISTS_SEPARATE_APPROVED_RETRY_ENTRY_REQUIRED')


def private_write(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2)


def private_dir(path):
    path=Path(path)
    if any(p.is_symlink() for p in [path,*path.parents]):raise Blocked('Symlink runtime ancestry')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    s=path.stat()
    if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:raise Blocked('Owner-only runtime directory required')
    return path


def host_guard(orchestrator):
    if not sys.stdin.isatty():raise Blocked('HUMAN_HOST_TERMINAL_REQUIRED')
    if os.getuid()==0:raise Blocked('NORMAL_NONROOT_HUMAN_USER_REQUIRED')
    sys.path.insert(0,str(Path(orchestrator)/'src'))
    from isolation_guard import environment
    evidence=environment()
    if evidence.get('state')!='HOST_CONTEXT':raise Blocked('HUMAN_HOST_CONTEXT_REQUIRED: '+json.dumps(evidence))
    if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):
        raise Blocked('PIDFD_REQUIRED_FOR_OWNED_PROCESS_STOP')
    return evidence


def require_idle_status(data,runtime):
    required={'runtime','paused','stopping','active_tasks','blocked','pending_recovery','task_counts'}
    if not isinstance(data,dict) or not required<=set(data):raise Blocked('COORDINATOR_STATUS_SCHEMA_UNKNOWN')
    if data['runtime']!=str(Path(runtime).resolve()):raise Blocked('COORDINATOR_RUNTIME_IDENTITY_MISMATCH')
    if any(type(data[k]) is not bool for k in ['paused','stopping']) or any(type(data[k]) is not list for k in ['active_tasks','blocked','pending_recovery']):
        raise Blocked('COORDINATOR_STATUS_TYPES_UNKNOWN')
    counts=data['task_counts']
    if not isinstance(counts,dict) or any(not isinstance(k,str) or type(v)is not int or v<0 for k,v in counts.items()):
        raise Blocked('COORDINATOR_COUNTS_UNKNOWN')
    if data['paused'] or data['stopping'] or data['active_tasks'] or data['blocked'] or data['pending_recovery'] or any(counts.get(k,0) for k in ['QUEUED','RUNNING','VERIFYING']):
        raise Blocked('COORDINATOR_BUSY_OR_UNKNOWN')
    return data


class Coordinator:
    def __init__(self,repo,record):
        self.repo=Path(repo);sys.path.insert(0,str(self.repo/'agents/local_llm'))
        from local_llm import Client, RUNTIME
        from model_runtime import Runtime
        import endpoint_config
        self.root=RUNTIME;self.rt=Runtime(runtime=RUNTIME);self.lock_client=Client(runtime=RUNTIME)
        p=endpoint_config.private_json(RUNTIME/'router-host-profile.json')
        self.orchestrator=Path(p['orchestrator_root'])
        self.control_root=self.orchestrator/record['coordinator_runtime_relative']
        self.mutated=False;self.lifecycle_unknown=False

    def guard(self):return host_guard(self.orchestrator)

    @contextmanager
    def locked(self):
        with self.lock_client.locked():yield

    def idle(self):
        self.rt.require_deployment()
        sys.path.insert(0,str(self.orchestrator/'src'))
        from control_socket import request
        s=request(self.control_root,'status',timeout=5)
        require_idle_status(s,self.control_root)
        deadline=time.monotonic()+10
        states=self.rt.snapshot(deadline)
        if states.get(MODEL)!='loaded' or any(v!='unloaded' for k,v in states.items() if k!=MODEL):
            raise Blocked('RESIDENT30B_ONLY_REQUIRED')
        self.rt._idle(MODEL,deadline);self.rt._threshold(preflight=True)
        return states

    def post_once(self,path,deadline):
        """Transport runs in the calling thread; monitor can abort, never submit."""
        if path not in {'/models/load','/models/unload'}:raise Blocked('FIXED_MODEL_LIFECYCLE_ONLY')
        stop=threading.Event();pressure=[]
        def observe():
            while not stop.wait(.5):
                try:self.rt._threshold()
                except Exception:
                    pressure.append('RESOURCE_OR_PROBE_FAILURE');self.rt.api.abort();return
        watcher=threading.Thread(target=observe,daemon=True);watcher.start()
        try:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise Blocked('LIFECYCLE_DEADLINE')
            result=self.rt.api.request('POST',path,{'model':MODEL},timeout=remaining)
            if pressure or not isinstance(result,dict) or result.get('success') is not True:
                raise Blocked('LIFECYCLE_RESPONSE_UNCONFIRMED')
        except BaseException:
            self.lifecycle_unknown=True;self.rt.api.abort();raise
        finally:
            stop.set();watcher.join(timeout=2)

    def unload(self):
        self.mutated=True
        deadline=time.monotonic()+30
        self.post_once('/models/unload',deadline)
        states=self.rt._wait(MODEL,'unloaded',deadline)
        if any(v!='unloaded' for v in states.values()):raise Blocked('ROUTER_NOT_EMPTY')
        return states

    def restore(self):
        """Caller already owns the common lock. Never call Runtime.prepare recursively."""
        if self.lifecycle_unknown:raise Blocked('LIFECYCLE_SUBMISSION_UNKNOWN_NO_AUTO_RESTORE')
        end=time.monotonic()+120
        states=self.rt.snapshot(end)
        # Reconcile a timed-out lifecycle read without reissuing the original operation.
        while any(v in {'loading','unloading'} for v in states.values()):
            if time.monotonic()>=end:raise Blocked('RESTORE_LIFECYCLE_UNKNOWN')
            time.sleep(.5);states=self.rt.snapshot(end)
        if any(v!='unloaded' for k,v in states.items() if k!=MODEL):raise Blocked('FOREIGN_MODEL_NO_AUTOMATIC_STOP')
        if states[MODEL]=='unloaded':
            self.rt._threshold(preflight=True)
            self.post_once('/models/load',end)
            states=self.rt._wait(MODEL,'loaded',end)
        if states[MODEL]!='loaded':raise Blocked('RESTORE_NOT_CONFIRMED')
        props=self.rt.read('/props?model='+MODEL+'&autoload=false',end)
        if props.get('model_alias')!=MODEL or props.get('default_generation_settings',{}).get('n_ctx')!=32768 or props.get('total_slots')!=1:
            raise Blocked('RESTORED_PROFILE_MISMATCH')
        self.rt._idle(MODEL,end)
        return {'status':'RESTORED','model_states':states,'resources':self.rt._threshold()}

    def uncertain(self,reason):self.lock_client.uncertain(reason)


def validate_pack(path,layers):
    m=json.loads((Path(path)/'manifest.json').read_text())
    if m.get('n_layers')!=layers or m.get('n_experts_per_layer')!=512:
        raise Blocked('PACK_GEOMETRY_MISMATCH')
    expected=layers*512*1382400
    if m.get('source',{}).get('shard1_sha256')!='69820c02ec7d0b45ef2ebb19d6620299db749fe2aded7f39f93c6b88b199b720' or m.get('source',{}).get('shard2_sha256')!='316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113':
        raise Blocked('BUILD_SOURCE_HASH_DOES_NOT_MATCH_PINNED_FLASH')
    if (Path(path)/'experts.bin').is_symlink() or (Path(path)/'experts.bin').stat().st_size!=expected:
        raise Blocked('PACK_EXPERT_LENGTH_MISMATCH')
    return {'layers':layers,'expert_bytes':expected,'dense_is_full_model_even_in_pilot':True}


def environment_for(verified,run):
    # Inherit no STRATA*, LD_PRELOAD, PYTHONPATH, credential or server-hook variables.
    env={k:os.environ[k] for k in ['LANG','LC_ALL','TZ'] if k in os.environ}
    env.update({'PATH':str(Path(sys.executable).parent)+':/usr/bin:/bin',
        'HOME':str(run),'TMPDIR':str(run/'tmp'),'XDG_CACHE_HOME':str(run/'cache'),
        'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','PYTHONNOUSERSITE':'1',
        'PYTHONPATH':str(verified['llama']/'gguf-py')+os.pathsep+str(verified['source']),
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'8',
        'STRATA_KEEP_LEFTOVERS':'1'})
    return env


class Trial:
    def __init__(self,repo,verified,coordinator,runner_factory=OwnedProcessRunner,probe=system_probe,run_root=None):
        self.repo=Path(repo);self.v=verified;self.c=coordinator;self.factory=runner_factory;self.probe=probe
        root=private_dir(run_root or self.repo/'agents/local_llm/.runtime/backend-trials')
        self.run_root=root
        if (root/'strata-UNCERTAIN.json').exists():raise Blocked('PRIOR_STRATA_UNKNOWN_REQUIRES_INSPECTION')
        self.run=private_dir(root/('strata-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]))
        for name in ['tmp','cache']:(self.run/name).mkdir(mode=0o700)
        self.results=[];self.safe_cleanup=True;self.started=time.monotonic()
        self.before=self.probe();self.finished_generations=0;self.requests=0;self.next_progress=0
        self.env=environment_for(verified,self.run)
        self.runner=self.factory(limits=Limits(),run_dir=self.run,probe=self.monitored_probe,poll_interval=.5,disk_baseline_bytes=0)

    def monitored_probe(self):
        r=self.probe()
        if time.monotonic()>=self.next_progress:
            self.next_progress=time.monotonic()+5
            self.log('resource_progress',mem_available=r.get('mem_available'),gpu_used=r.get('gpu_used'),gtt_used=r.get('gtt_used'),swap_used=r.get('swap_used'))
        return r

    def log(self,event,**data):
        row={'event':event,'elapsed_seconds':round(time.monotonic()-self.started,3),**data}
        print(json.dumps(row,ensure_ascii=False),flush=True)
        p=self.run/'events.jsonl'
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')

    def remaining(self,requested):
        left=WHOLE_SECONDS-(time.monotonic()-self.started)-165
        if left<=0:raise Blocked('WHOLE_TRIAL_DEADLINE_RECOVERY_RESERVED')
        return min(requested,left)

    def safety(self):
        r=self.probe()
        if r['mem_available']<24*GIB or r['gpu_used'] is None or r['gpu_used']>58*GIB or r['swap_used']>self.before['swap_used']:
            raise Blocked('STAGE_PREFLIGHT_RESOURCE_LIMIT')
        if sum(p.stat().st_size for p in self.run.rglob('*') if p.is_file() and not p.is_symlink())>70*GIB:
            raise Blocked('WHOLE_RUN_DISK_LIMIT')
        return r

    def stage(self,name,argv):
        self.safety();self.log('stage_start',stage=name)
        self.safe_cleanup=False
        result=self.runner.run(argv,str(self.v['source']),self.remaining(STAGES[name]),env=self.env)
        self.safe_cleanup=result.get('cleanup',{}).get('complete',result.get('status')=='BLOCKED')
        self.results.append({'stage':name,**result});private_write(self.run/(name+'.json'),result)
        self.log('stage_end',stage=name,status=result['status'],reason=result.get('reason'))
        if result['status']!='COMPLETED':raise Blocked(name+':'+str(result.get('reason')))
        self.safety()
        return result

    def before_unload(self):
        """Optional fixed replay validation while the resident model remains loaded."""
        return None

    def build_packs(self):
        """Build only new outputs; replay subclasses may reuse a separately verified pilot."""
        source=self.v['source'];gguf=str(self.v['shards'][0]);py=sys.executable
        full=self.run/'full'
        for label,out,layers in [('pilot',self.run/'pilot',1),('full',full,48)]:
            self.stage(label+'_build',[py,'-B',str(source/'tools/strata_pack.py'),'build','--gguf',gguf,'--out',str(out),'--layers',str(layers)])
            validate_pack(out,layers)
            self.stage(label+'_verify',[py,'-B',str(source/'tools/strata_pack.py'),'verify','--gguf',gguf,'--out',str(out)])
        return full

    def execute(self):
        outcome={'status':'FAILED','environment':'NOT_RUN','quality':'UNASSESSED','generation_requests':0,
                 'restoration':'NOT_NEEDED','run_directory':str(self.run),'automatic_retry':False,'code_executed':False}
        fingerprints=[(p.stat().st_dev,p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in self.v['shards']]
        try:
            with self.c.locked():
                self.c.idle();self.safety()
                if __import__('shutil').disk_usage(self.run).free<100*GIB:raise Blocked('FREE_DISK_BELOW100GIB')
                try:
                    private_write(self.run/'import-input.json',{})
                    self.stage('imports',[sys.executable,'-B',str(Path(__file__).with_name('strata_shim.py')),'check',
                        '--source',str(self.v['source']),'--gguf',str(self.v['shards'][0]),'--pack',str(self.run),
                        '--input',str(self.run/'import-input.json'),'--output',str(self.run/'import-output.json')])
                    self.before_unload()
                    self.log('unload30b_intent');self.c.unload();self.log('unload30b_confirmed')
                    source=self.v['source'];gguf=str(self.v['shards'][0]);py=sys.executable
                    full=self.build_packs()
                    self.stage('index',[py,'-B',str(source/'tools/pack_index.py'),'--pack',str(full)])
                    self.stage('tokenizer',[py,'-B',str(source/'tools/strata_tokenizer.py'),'--gguf',gguf,'--out',str(full),'--check'])
                    sys.path.insert(0,str(self.repo/'agents/local_llm'))
                    from local_llm import policy_context
                    policy=policy_context('draft');private_write(self.run/'prompt.json',{'messages':[
                        {'role':'system','content':policy['system']},{'role':'user','content':'Reply with exactly '+ACK+' and no other text.'}],
                        'policy':policy['metadata']})
                    shim=Path(__file__).with_name('strata_shim.py')
                    common=['--source',str(source),'--gguf',gguf,'--pack',str(full)]
                    self.stage('encode',[py,'-B',str(shim),'encode',*common,'--input',str(self.run/'prompt.json'),'--output',str(self.run/'encoded.json')])
                    encoded=json.loads((self.run/'encoded.json').read_text());ids=encoded['prompt_ids']
                    if encoded.get('stop_ids')!=[248044,248046]:raise Blocked('PINNED_STOP_TOKEN_MISMATCH')
                    self.safety();self.log('native_start_intent')
                    argv=[str(self.v['exe']),'--pack',str(full),'--native',gguf,'--ple-gguf',str(self.v['shards'][1]),
                          '--mmap-experts','--ple-io','direct','--expert-cache','1024','--max-context','8192','--prefill','512','--eos-ids','248044,248046','--serve']
                    if self.remaining(180)<180:raise Blocked('NATIVE180_SECONDS_PLUS_RECOVERY_NOT_AVAILABLE')
                    self.safe_cleanup=False
                    result=self.runner.rawserve(argv,str(source),ids,start_timeout=self.remaining(90),generation_timeout=self.remaining(90),
                        stop_timeout=45,max_tokens=128,env=self.env,required_startup_marker='experts via mmap (--mmap-experts;')
                    self.safe_cleanup=result.get('cleanup',{}).get('complete',False)
                    self.requests=result['generation_requests'];self.results.append({'stage':'native',**result})
                    private_write(self.run/'native.json',result)
                    outcome['generation_requests']=self.requests
                    if result.get('root_identity') is not None:outcome['environment']='FAIL'
                    if result['status']=='UNKNOWN':
                        outcome.update(status='UNKNOWN',environment='UNKNOWN',generation_uncertain=True)
                        private_write(self.run_root/'strata-UNCERTAIN.json',{'run_directory':str(self.run),'generation_requests':self.requests,'automatic_retry':False,'reason':result.get('reason')})
                    if result['status']!='COMPLETED':raise Blocked('native:'+str(result.get('reason')))
                    self.finished_generations=1
                    private_write(self.run/'tokens.json',{'token_ids':result['token_ids'],'finish':result['done']['finish']})
                    self.stage('decode',[py,'-B',str(shim),'decode',*common,'--input',str(self.run/'tokens.json'),'--output',str(self.run/'decoded.json')])
                    text=json.loads((self.run/'decoded.json').read_text())['content']
                    outcome.update(status='COMPLETED',environment='PASS',quality='ACK_ONLY_PASS' if text==ACK and result['done']['finish']=='stop' else 'ACK_FORMAT_FAIL',
                                   content=text,model_quality_general='NOT_ESTIMATED')
                except BaseException as exc:
                    outcome['reason']=type(exc).__name__+':'+str(exc)[:400]
                    self.log('trial_failed',reason=outcome['reason'])
                finally:
                    if not self.c.mutated and not self.safe_cleanup:
                        self.c.uncertain('STRATA_TRIAL_PREFLIGHT_OWNED_CLEANUP_UNCERTAIN');outcome.update(status='UNKNOWN',restoration='RESIDENT_UNCHANGED_OWNED_PROCESSES_UNKNOWN')
                    if self.c.mutated:
                        if self.safe_cleanup:
                            try:
                                self.log('restore30b_intent');outcome['restoration']=self.c.restore();self.log('restore30b_confirmed')
                            except BaseException as exc:
                                self.c.uncertain('STRATA_TRIAL_RESTORE_UNCERTAIN');outcome['restoration']='UNKNOWN';outcome['status']='UNKNOWN';outcome['restore_error']=type(exc).__name__
                        else:
                            self.c.uncertain('STRATA_TRIAL_OWNED_CLEANUP_UNCERTAIN');outcome.update(status='UNKNOWN',restoration='BLOCKED_OWNED_PROCESSES_REMAIN')
        except BaseException as exc:
            outcome['reason']=type(exc).__name__+':'+str(exc)[:400]
        try:unchanged=fingerprints==[(p.stat().st_dev,p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in self.v['shards']]
        except OSError:unchanged=False
        try:after=self.probe()
        except (OSError,ValueError,KeyError):after={'status':'UNAVAILABLE'}
        outcome.update(source_metadata_unchanged=unchanged,resources_before=self.before,resources_after=after,elapsed_seconds=time.monotonic()-self.started,
                       generated_pack_retained=True,completed_generations=self.finished_generations,cleanup_scope='observed owned PID/starttime tree; no namespace or hard memory cap')
        if not unchanged:
            outcome['source_integrity_error']='SOURCE_METADATA_CHANGED'
            # Source integrity failure cannot establish whether a process/request
            # or restoration completed. Preserve the more restrictive UNKNOWN.
            if outcome['status']!='UNKNOWN':
                outcome.update(status='FAILED',reason='SOURCE_METADATA_CHANGED')
        private_write(self.run/'summary.json',outcome)
        self.log('finished',status=outcome['status'],generation_requests=self.requests,restoration=outcome['restoration'])
        return outcome


def main():
    global RUN_STARTED
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',type=Path);p.add_argument('--run-approved',action='store_true');p.add_argument('--check-assets',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[3]
    if not a.assets:
        print(json.dumps({'status':'PREPARED_NOT_AUTHORIZED','fixed_source':SOURCE_COMMIT,'engine_sha256':assets.ENGINE_SHA,'requires':'Individual software approval, verified operator record, human host terminal','generation_requests':0}));return 0
    if a.run_approved:require_initial_attempt_unconsumed(repo)
    v=assets.verify(a.assets,repo)
    if not a.run_approved:
        print(json.dumps({'status':'ASSETS_CHECKED_NO_EXECUTION','sources':v['source_checks'],'dependencies':v['dependencies'],'generation_requests':0}));return 0
    if a.check_assets:raise Blocked('Choose check or approved run, not both')
    c=Coordinator(repo,v['record']);evidence=c.guard()
    # Restrict children/new files to owner; do not change pre-existing permissions.
    os.umask(0o077)
    def interrupted(signum,frame):raise KeyboardInterrupt('HOST_TRIAL_SIGNAL_'+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    RUN_STARTED=True
    result=Trial(repo,v,c).execute()
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status']=='COMPLETED' and result['restoration']!='UNKNOWN' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'UNKNOWN' if RUN_STARTED else 'BLOCKED','reason':type(exc).__name__+':'+str(exc)[:400],'generation_requests':None if RUN_STARTED else 0,'automatic_retry':False}),file=sys.stderr);raise SystemExit(1)
