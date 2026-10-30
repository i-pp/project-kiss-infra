"""Approved fixed-profile HTTP lifecycle. No Docker, subprocess or namespace APIs."""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import stat
import threading
import time
import endpoint_config
from local_llm import Client, HttpApi, LocalError, RUNTIME, GIB, resources, policy_context

PROFILES = {'qwen-coder-30b':'kiss-qwen3-coder-30b',
            'gpt-oss-120b':'kiss-b3-gpt-oss-120b',
            'qwen-coder-next':'kiss-b3-qwen-coder-next'}
BUDGETS = {'qwen-coder-30b':(76,7), 'gpt-oss-120b':(218,20), 'qwen-coder-next':(158,20)}
PREPARE_SECONDS = 120
IMAGE = 'sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15'


class Runtime:
    def __init__(self, api=None, probe=resources, runtime=RUNTIME, policy_provider=policy_context,
                 client_factory=Client, confirmation=None, interval=1, api_factory=HttpApi):
        self.api, self.probe, self.root = api or HttpApi(runtime=runtime), probe, Path(runtime)
        self.policy_provider, self.client_factory = policy_provider, client_factory
        self.confirmation, self.interval, self.api_factory = confirmation, interval, api_factory

    def confirmed(self):
        if self.confirmation is not None:return self.confirmation()
        try:
            return endpoint_config.route(self.root).get('mode')=='router'
        except (OSError,ValueError,TypeError):return False

    def alias(self,profile):
        if not isinstance(profile,str) or profile not in PROFILES:
            raise LocalError('UNKNOWN_PROFILE','Select a fixed profile')
        return PROFILES[profile]

    def require_deployment(self):
        if not self.confirmed():
            raise LocalError('ROUTER_DEPLOYMENT_PENDING','Human deployment and read-only verification are pending')

    def read(self,path,deadline):
        remaining=min(2,deadline-time.monotonic())
        if remaining<=0:raise LocalError('TIMEOUT','Read deadline reached')
        return self.api.request('GET',path,timeout=remaining)

    def snapshot(self,deadline=None):
        deadline=deadline or time.monotonic()+8
        if self.read('/health',deadline).get('status')!='ok':raise LocalError('MODEL_UNAVAILABLE','Router not healthy')
        rows=self.read('/models',deadline).get('data')
        if not isinstance(rows,list) or len(rows)!=3 or {r.get('id') for r in rows}!=set(PROFILES.values()):
            raise LocalError('ROUTER_CONTRACT_MISMATCH','Router must advertise only the three fixed profiles')
        states={r['id']:r.get('status',{}).get('value') for r in rows}
        if any(v not in {'loaded','unloaded','loading','unloading'} for v in states.values()):
            raise LocalError('ROUTER_CONTRACT_MISMATCH','Unknown model state')
        if sum(v!='unloaded' for v in states.values())>1:
            raise LocalError('ROUTER_CONTRACT_MISMATCH','More than one model is active')
        return states

    def status(self,profile):
        alias=self.alias(profile)
        if not self.confirmed():
            return {'profile':profile,'model':alias,'status':'BLOCKED','reason':'ROUTER_DEPLOYMENT_PENDING',
                    'deployment_confirmed':False,'executed':False,'generation_requests':0,'automatic_retry':False}
        try:
            states=self.snapshot()
            return {'profile':profile,'model':alias,'status':'READY' if states[alias]=='loaded' else 'NOT_LOADED',
                    'deployment_confirmed':True,'model_states':states,'blocked_uncertain':(self.root/'UNCERTAIN.json').exists(),
                    'resources':self.probe(),'generation_requests':0,'automatic_retry':False}
        except LocalError as exc:
            return {'profile':profile,'model':alias,'status':'UNAVAILABLE','reason':exc.code,
                    'generation_requests':0,'automatic_retry':False}

    def _threshold(self,preflight=False):
        sample=self.probe()
        if sample['available_bytes']<(24 if preflight else 16)*GIB or sample['gpu_used_bytes']>58*GIB:
            raise LocalError('RESOURCE_LIMIT','Existing memory/GPU thresholds are not satisfied')
        return sample

    def _post(self,path,alias,deadline):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise LocalError('TIMEOUT','Operation deadline reached')
        result=queue.Queue(maxsize=1);cancelled=threading.Event()
        def send():
            try:
                if cancelled.is_set() or deadline-time.monotonic()<=0: raise LocalError('TIMEOUT','Dispatch deadline reached')
                result.put((True,self.api.request('POST',path,{'model':alias},timeout=max(.001,deadline-time.monotonic()))))
            except Exception as exc:result.put((False,exc))
        worker=threading.Thread(target=send,daemon=True);worker.start();bad=0
        try:
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise LocalError('TIMEOUT','Model operation deadline reached')
                try:
                    ok,value=result.get(timeout=min(self.interval,remaining))
                    if not ok:raise value
                    if not isinstance(value,dict) or value.get('success') is not True:
                        raise LocalError('UNCERTAIN','Lifecycle response did not confirm success')
                    return
                except queue.Empty:
                    try:self._threshold();bad=0
                    except LocalError:
                        bad+=1
                        if bad>=3:raise LocalError('RESOURCE_LIMIT','Runtime pressure for three samples')
        except Exception:
            cancelled.set();self.api.abort();worker.join(timeout=2)
            raise

    def _wait(self,alias,state,deadline):
        bad=0
        while True:
            states=self.snapshot(deadline)
            if states[alias]==state:return states
            try:self._threshold();bad=0
            except LocalError:
                bad+=1
                if bad>=3:raise
            remaining=deadline-time.monotonic()
            if remaining<=0:raise LocalError('TIMEOUT','Model state not confirmed')
            time.sleep(min(self.interval,remaining))

    def _idle(self,alias,deadline):
        slots=self.read('/slots?model='+alias+'&autoload=false',deadline)
        if not isinstance(slots,list) or len(slots)!=1 or slots[0].get('is_processing') is not False:
            raise LocalError('BUSY','Model has active or unknown work')

    def cleanup(self,alias,deadline):
        """Unload only the fixed model from this operation; never restore or retry."""
        outcome={'model':alias,'cleanup':'UNKNOWN','automatic_retry':False}
        try:
            states=self.snapshot(deadline)
            if alias not in states:raise LocalError('UNKNOWN_PROFILE','Fixed model only')
            if states[alias]=='unloaded':outcome['cleanup']='ALREADY_UNLOADED'
            else:
                self._post('/models/unload',alias,deadline)
                self._wait(alias,'unloaded',deadline)
                outcome['cleanup']='UNLOADED'
        except Exception:pass
        path=self.root/('cleanup-'+str(time.time_ns())+'.json')
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:json.dump(outcome,stream)
        except OSError:pass
        return outcome

    def prepare(self,profile):
        alias=self.alias(profile);self.require_deployment()
        started=time.monotonic();hard=started+PREPARE_SECONDS;work=hard-22
        lock=Client(runtime=self.root)
        with lock.locked():
            policy=self.policy_provider('draft')['metadata']
            before=self._threshold(preflight=True)
            states=self.snapshot(work)
            if any(v in {'loading','unloading'} for v in states.values()):raise LocalError('BUSY','Lifecycle work active')
            active=next((m for m,v in states.items() if v=='loaded'),None)
            if active:self._idle(active,work)
            mutated=False
            try:
                if active!=alias:
                    if active:
                        mutated=True
                        self._post('/models/unload',active,min(work,time.monotonic()+12))
                        self._wait(active,'unloaded',min(work,time.monotonic()+8))
                    self._threshold(preflight=True)
                    mutated=True
                    self._post('/models/load',alias,min(work,time.monotonic()+90))
                    states=self._wait(alias,'loaded',work)
                props=self.read('/props?model='+alias+'&autoload=false',work)
                if props.get('model_alias')!=alias or props.get('default_generation_settings',{}).get('n_ctx')!=32768 or props.get('total_slots')!=1:
                    raise LocalError('ROUTER_CONTRACT_MISMATCH','Loaded model identity or context differs')
                return {'status':'READY','profile':profile,'model':alias,'already_loaded':active==alias,
                        'seconds':time.monotonic()-started,'model_states':states,'policy':policy,
                        'resources_before':before,'resources_after':self._threshold(),
                        'generation_requests':0,'automatic_retry':False}
            except Exception as exc:
                if mutated:
                    lock.uncertain(getattr(exc,'code','UNCERTAIN'))
                    self.api.abort()
                    self.cleanup(alias,hard)
                if isinstance(exc,LocalError):raise
                raise LocalError('UNCERTAIN','Lifecycle outcome requires inspection') from None

    def generate(self,profile,task,prompt,max_tokens=256):
        alias=self.alias(profile);self.require_deployment()
        # No lifecycle side effect here; Client rechecks identity under the common lock.
        states=self.snapshot()
        if states[alias]!='loaded':raise LocalError('MODEL_NOT_LOADED','Prepare the selected model explicitly first')
        core,cleanup=BUDGETS[profile]
        def recover(model):
            old=self.api
            self.api=old.fork() if isinstance(old,HttpApi) else self.api_factory()
            try:self.cleanup(model,time.monotonic()+cleanup)
            finally:self.api=old
        client=self.client_factory(api=self.api,runtime=self.root,model=alias,operation_timeout=core,
            policy_provider=self.policy_provider,probe=self.probe,failure_cleanup=recover,require_idle=True)
        data=client.generate(task,prompt,max_tokens);data['profile']=profile
        return data


def confirm_deployment(evidence,runtime=RUNTIME):
    """Verify the receipt already published by human maintenance. No registration/write."""
    try:endpoint_config.validate_receipt(evidence,runtime)
    except (OSError,ValueError,TypeError,KeyError):
        raise LocalError('INVALID_INPUT','Verified internal route receipt required') from None
    if endpoint_config.route(runtime)!=evidence:
        raise LocalError('INVALID_INPUT','Receipt must already be published by human maintenance')
    r=Runtime(runtime=runtime,confirmation=lambda:True)
    lock=Client(runtime=runtime)
    with lock.locked():
        states=r.snapshot()
        if states[PROFILES['qwen-coder-30b']]!='loaded':raise LocalError('MODEL_UNAVAILABLE','Resident30B must be loaded first')
        r._idle(PROFILES['qwen-coder-30b'],time.monotonic()+5)
        Client(runtime=runtime).status()
    return {'deployment_confirmed':True,'model_states':states,'generation_requests':0}
