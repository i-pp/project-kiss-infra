"""Maintained zero-generation warm-cache vLLM measurement. Default is inert."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

import host_api_trial as h
from total_swap_trial import TotalSwapTrial
from total_swap_monitor import TotalSwapMonitor
from warm_cache_limits import TotalSwapLimits, AUTHORIZATION
from cached_next_assets import CachedNextVerifier
from paging_telemetry import PagingTelemetry
from owned_memory_telemetry import OwnedMemoryTelemetry

REQUEST = 'Sentinel_9a32f7c656b881919a3960689c547110'
SCOPE = 'VLLM_NEXT_WARM_CACHE_STARTUP_ZERO_GENERATION_20261101'
DIGEST = hashlib.sha256((SCOPE+REQUEST).encode()).hexdigest()
BASE_SHA = '5fdcd0f0cac68c2b7c9c28df64756c44ccba936b0759d642d7bb17804a64ce5b'


class Monitor32(TotalSwapMonitor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Instance-only policy. Historical 8GB modules and services unchanged.
        self.limits = TotalSwapLimits(self.sampler.sample(force=True)['observed'])


class LoadBoundaryDriver:
    def __init__(self, inner, verifier, mark):
        object.__setattr__(self, 'inner', inner)
        object.__setattr__(self, 'verifier', verifier)
        object.__setattr__(self, 'mark', mark)
    def __getattr__(self, name): return getattr(self.inner, name)
    def __setattr__(self, name, value): setattr(self.inner, name, value)
    def start(self, cid):
        self.verifier.assert_unchanged()
        self.mark('pre_load_identity_verified')
        self.mark('container_start_requested')
        return self.inner.start(cid)


def parse_server_phases(capture):
    text = capture.get('stdout','')+'\n'+capture.get('stderr','')
    def number(pattern):
        match=re.search(pattern,text)
        return float(match.group(1)) if match else None
    return {'weights_load_seconds': number(r'Loading weights took ([0-9.]+) seconds'),
            'engine_profile_kv_warmup_seconds':number(r'init engine .*? took ([0-9.]+) s'),
            'gpu_initialization_seconds':None,
            'gpu_initialization_status':'UNAVAILABLE_NOT_SEPARATELY_INSTRUMENTED',
            'source':'bounded server stdout/stderr; no inferred absent metrics',
            'overlap':'loader/engine/GPU phases may overlap; do not sum as disjoint times',
            'logs_complete':capture.get('complete_stream') is True}


class WarmCacheTrial(TotalSwapTrial):
    OPERATOR_SHA = DIGEST
    TRIAL_AUTHORIZATION = REQUEST
    def __init__(self, record, coordinator, driver, http, run, write, policy,
                 monitor, verifier, **kwargs):
        self.monitor=monitor;self.verifier=verifier;self.phase_marks=[]
        self.original_write=self.measurement_write(write)
        self.logical_checks=0;self.last_sample_id=None;self.seen_sample_ids=set();self.releasing=False
        h.Trial.__init__(self,record,'vllm',coordinator,
            LoadBoundaryDriver(driver,verifier,self.mark),http,monitor.raw,run,self.scoped_write,policy,
            verify=self.verify_cached,unchanged=verifier.unchanged,operator_sha256=DIGEST,**kwargs)
        self.paging=PagingTelemetry(read=lambda:monitor.raw()['paging'])
        self.owned_memory=OwnedMemoryTelemetry()
    def mark(self,event):
        self.phase_marks.append({'event':event,'elapsed_seconds':self.clock()-self.start_time})
    def verify_cached(self,directory,check):
        self.mark('verification_start')
        result=self.verifier(directory,check=check)
        self.mark('verification_complete')
        if self.verifier.result.get('mode')!='METADATA_CACHE_HIT':
            raise h.Blocked('CPU_PRIMING_COMPLETED_BUT_NO_WARM_HIT_NO_LIFECYCLE')
        return result
    def log(self,event,**values):
        if event=='unload30b_intent':
            self.verifier.assert_unchanged()
            self.mark('pre_unload_identity_verified')
        if event=='start_owned_intent':
            self.verifier.assert_unchanged()
        if event=='resource_threshold_exceeded':values['approval']=AUTHORIZATION
        super().log(event,**values)
    def startup(self,end):
        self.mark('api_wait_start')
        super().startup(end)
        self.mark('api_ready')
        self.verifier.assert_unchanged()
        self.mark('post_load_identity_verified')
    def generate_once(self):
        # Base lifecycle calls this hook after API readiness. Never submit POST.
        self.safety(force=True);self.verifier.assert_unchanged()
        return {'environment':'PASS','quality':'NOT_TESTED_ZERO_GENERATION',
                'measurement':'WARM_CACHE_STARTUP_ONLY','model_quality_general':'NOT_ESTIMATED'}
    def measurement_write(self,sink):
        def write(path,payload):
            if path.name in {'resource-policy.json','summary.json'}:
                payload['swap_authorization']=AUTHORIZATION
            sink(path,payload)
            if path.name=='summary.json':
                capture_path=self.run/'server-log-tail.json'
                capture=json.loads(capture_path.read_text()) if capture_path.exists() else {}
                verification=self.verifier.result
                report={'scope':SCOPE,'phase_marks':self.phase_marks,
                        'verification':{k:v for k,v in verification.items() if k!='binding'} if verification else None,
                        'server_phases':parse_server_phases(capture),
                        'generation_requests':self.post_intents,'no_decode_benchmark':True}
                marks={p['event']:p['elapsed_seconds'] for p in self.phase_marks}
                report['container_start_to_api_ready_seconds']=(marks['api_ready']-marks['container_start_requested']
                    if 'api_ready' in marks and 'container_start_requested' in marks else None)
                sink(self.run/'startup-measurement.json',report)
        return write


def reserve_measurement(root,run):
    path=Path(root)/('warm-cache-startup-'+DIGEST+'.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump({'scope':SCOPE,'request':REQUEST,'run':str(run),'attempt_limit':1,
                   'generation_request_limit':0,'automatic_retry':False},stream)
        stream.flush();os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-coordinated-once',action='store_true')
    parser.add_argument('--cache-dir',type=Path)
    args=parser.parse_args(argv)
    if not args.execute_coordinated_once:
        print(json.dumps({'status':'PREPARED_NO_EXECUTION','scope':SCOPE,'whole_seconds':900,
              'startup_seconds':300,'generation_requests':0,'requires_mcp_recovery_and_gpu_coordination':True}))
        return 0
    if args.cache_dir is None:raise h.Blocked('PRIVATE_CACHE_REQUIRED')
    started=time.monotonic()
    # Fixed installed project and reviewed image/model only; no command/URL option.
    repo=Path(__file__).resolve().parents[3]
    record=h.operator_record(repo/'agents/local_llm/.runtime/next-vllm-jit-trial-approved-20261030.json',BASE_SHA,backend='vllm')
    Coordinator,directory,write,_=h.helpers();c=Coordinator(repo,record);c.guard()
    root=directory(repo/'agents/local_llm/.runtime/backend-api-trials')
    marker=root/('warm-cache-startup-'+DIGEST+'.json')
    if marker.exists() or marker.is_symlink():raise h.Blocked('MEASUREMENT_ALREADY_RESERVED_NO_RETRY')
    run=directory(root/('vllm-cache-measurement-'+uuid.uuid4().hex))
    monitor=Monitor32();monitor.attach_coordinator(c)
    sys.path.insert(0,str(repo/'agents/local_llm'))
    from local_llm import policy_context
    verifier=CachedNextVerifier(args.cache_dir)
    def reserve():
        reserve_measurement(root,run)
    h.STARTUP_SECONDS=dict(h.STARTUP_SECONDS,vllm=300)
    h.install_sigterm_handler()
    from trial_output import capture_run_output
    with capture_run_output(run) as output:
        trial=WarmCacheTrial(record,c,h.Docker(c.guard),h.LocalHTTP(),run,write,
            policy_context,monitor,verifier,reserve_attempt=reserve,start_time=started)
        result=trial.execute();print(json.dumps(result),flush=True)
        code=0 if result['status']=='COMPLETED' else 1;output.finish(code)
        return code


if __name__=='__main__':raise SystemExit(main())
