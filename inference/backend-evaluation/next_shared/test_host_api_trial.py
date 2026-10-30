"""CPU fakes only: no Docker command, GPU, HTTP connection or model is used."""
from contextlib import contextmanager,redirect_stdout
import copy
import hashlib
import io
import json
import os
import sys
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import acquire_next_host as acquire
import fixed_trial_assets as assets
import host_api_trial as h


def write(path,data):
    with Path(path).open('x') as f:json.dump(data,f)


def healthy():return {'mem_available':40*h.GIB,'gpu_used':2*h.GIB,'swap_used':0}


def record(root):
    project=root/'project';(project/'agents/local_llm').mkdir(parents=True,exist_ok=True)
    runtimes={}
    for backend in ('vllm','sglang'):
        runtimes[backend]={'image_ref':'sha256:'+'1'*64,'image_id':'sha256:'+'1'*64,
            'source_commit':assets.SOURCE[backend],'source_dependency_match_reviewed':True,
            'bootstrap_complete_reviewed':True,'dependency_versions':{'compressed-tensors':'0.17.0' if backend=='vllm' else '0.15.0',
            'torch':'2.12.0' if backend=='vllm' else '2.9.1','triton':'3.5.1',
            'rocm':'7.2.3' if backend=='vllm' else '7.2.4','transformers':'5.17.0'}}
    return {'schema_version':1,'project_root':str(project),'model_dir':str(project/assets.MODEL_RELATIVE),
        'coordinator_runtime_relative':'.runtime/reviewed-coordinator',
        'review':{k:True for k in ['fixed_weight_acquisition_reviewed','human_host_docker_trial_reviewed',
          'resident30b_unload_restore_reviewed','temporary_owned_internal_api_reviewed','fixed_jit_cache_exec_reviewed']},'runtimes':runtimes}


class Coordinator:
    def __init__(self):self.mutated=False;self.events=[];self.restore_fails=False
    def guard(self):self.events.append('guard');return {'state':'HOST_CONTEXT'}
    @contextmanager
    def locked(self):
        self.events.append('lock')
        try:yield
        finally:self.events.append('unlock')
    def idle(self):self.events.append('idle')
    def unload(self):self.events.append('unload');self.mutated=True
    def restore(self):
        self.events.append('restore')
        if self.restore_fails:raise OSError('fixture')
        return {'status':'RESTORED'}
    def uncertain(self,reason):self.events.append('uncertain:'+reason)


class Driver:
    def __init__(self):
        self.row=None;self.events=[];self.mode=None;self.identity=None;self.clients_reaped=True
    def image(self,ref):
        self.events.append('image')
        return {'Id':'sha256:'+'1'*64,'Config':{'Volumes':{'/surprise':{}} if self.mode=='anonymous_volume' else {}}}
    def gpu_metadata(self):
        if self.mode=='missing_gpu':raise h.Blocked('FIXED_GPU_DEVICE_UNAVAILABLE')
        return [{'path':'/dev/kfd','fixture':True}]
    def network(self):
        net={'Id':'c'*64,'Name':h.NETWORK,'Internal':True,'Driver':'bridge','Scope':'local',
             'IPAM':{'Config':[{'Subnet':'172.29.0.0/24'}]},'Containers':{}}
        if self.row:
            net['Containers'][self.row['Id']]={'Name':self.row['Name'][1:],'EndpointID':'e'*64,'IPv4Address':'172.29.0.7/24'}
        if self.mode=='network_external':net['Internal']=False
        return net
    def find(self,name):self.events.append('inspect');return copy.deepcopy(self.row)
    def create(self,identity,r,backend):
        self.events.append('create');self.identity=identity.copy()
        if self.mode=='create_unknown_absent':raise h.Unknown('fixture')
        if self.mode=='create_sigterm_absent':assets.on_terminate(15,None)
        args=h.server_argv(backend)
        self.row={'Id':'a'*64,'Name':'/'+identity['name'],'Image':r['runtimes'][backend]['image_id'],
          'Config':{'Labels':{h.LABEL+'token':identity['token'],h.LABEL+'owner':identity['owner'],h.LABEL+'backend':backend},
            'Entrypoint':[args[0]],'Cmd':args[1:],'User':str(os.getuid())+':'+str(os.getgid()),
            'Healthcheck':{'Test':['NONE']}},'State':{'Running':False,'Status':'created','Pid':0},
          'HostConfig':{'Memory':32*h.GIB,'MemorySwap':32*h.GIB,'Privileged':False,'NetworkMode':h.NETWORK,
            'ReadonlyRootfs':True,'Tmpfs':{'/tmp':'rw,noexec,nosuid,nodev,size=2g',
                '/jit-cache':'rw,exec,nosuid,nodev,size=512m,mode=0700,uid='+str(os.getuid())+',gid='+str(os.getgid())},
            'PidsLimit':512,'NanoCpus':8_000_000_000,'Init':True,
            'IpcMode':'private','CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],
            'PortBindings':{}},
          'NetworkSettings':{'Networks':{h.NETWORK:{'NetworkID':'c'*64,'EndpointID':'e'*64,'IPAddress':'172.29.0.7','IPPrefixLen':24}}},
          'Mounts':[{'Source':r['model_dir'],'Destination':'/models/next-int4','RW':False}]}
        if self.mode=='foreign_token':self.row['Config']['Labels'][h.LABEL+'token']='foreign'
        if self.mode=='memory_swap_unlimited':self.row['HostConfig']['MemorySwap']=-1
        if self.mode=='unexpected_healthcheck':self.row['Config']['Healthcheck']={'Test':['CMD','unexpected']}
        return self.row['Id']
    def start(self,cid):
        self.events.append('start');self.row['State']={'Running':True,'Status':'running','Pid':42}
        if self.mode=='start_unknown':raise h.Unknown('fixture')
    def stop(self,cid,timeout=15):
        self.events.append('stop')
        if self.mode in ('stop_timeout','survivor'):raise h.Unknown('client timeout, container still alive')
        self.row['State']={'Running':False,'Status':'exited','Pid':0}
    def kill(self,cid,timeout=5):
        self.events.append('kill')
        if self.mode=='survivor':raise h.Unknown('fixture')
        self.row['State']={'Running':False,'Status':'exited','Pid':0}
    def remove(self,cid,timeout=5):
        self.events.append('remove')
        if self.mode=='remove_unknown_present':raise h.Unknown('fixture')
        self.row=None
    def logs(self,cid,timeout=3):self.events.append('logs');return 'fixture server stdout/stderr, never executed'


class HTTP:
    def __init__(self):self.gets=0;self.posts=0;self.body=None;self.mode=None;self.aborted=threading.Event();self.post_thread=None
    def arm(self):self.aborted.clear()
    def abort(self):self.aborted.set()
    def bind_route(self,route,confirm):self.route=route;self.confirm=confirm
    def request(self,method,path,body=None,timeout=2):
        if method=='GET':
            self.gets+=1
            if self.mode=='wait_for_startup_resource_abort':
                if not self.aborted.wait(2):raise RuntimeError('startup monitor did not abort')
                raise TimeoutError('startup resource abort')
            if self.mode=='not_ready':raise OSError('fixture')
            return {'data':[{'id':h.MODEL_ALIAS}]}
        self.posts+=1;self.body=body;self.post_thread=threading.get_ident()
        if self.mode=='wait_for_resource_abort':
            if not self.aborted.wait(2):raise RuntimeError('watcher did not abort')
            raise TimeoutError('resource abort')
        if self.mode=='post_unknown':raise TimeoutError('fixture')
        return {'choices':[{'message':{'content':'wrong' if self.mode=='bad_ack' else h.ACK},'finish_reason':'stop'}],
                'usage':{'completion_tokens':8}}


class Clock:
    def __init__(self):self.n=0
    def now(self):return self.n
    def sleep(self,n):self.n+=n


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.r=record(self.root)
        self.c=Coordinator();self.d=Driver();self.http=HTTP();self.clock=Clock()
    def tearDown(self):self.temp.cleanup()
    def execute(self,backend='vllm',probe=healthy,verify=lambda _,**kw:[],start_time=None,reserve=None):
        run=self.root/('run-'+str(len(list(self.root.glob('run-*')))));run.mkdir()
        t=h.Trial(self.r,backend,self.c,self.d,self.http,probe,run,write,
             lambda _: {'system':'COMMON POLICY FIXTURE','metadata':{'sha256':'fixture'}},
             verify=verify,unchanged=lambda _:True,clock=self.clock.now,sleep=self.clock.sleep,
             network_profile={'name':h.NETWORK,'id':'c'*64},start_time=start_time,reserve_attempt=reserve)
        with redirect_stdout(io.StringIO()):result=t.execute()
        return t,result
    def test_both_backends_one_post_policy_restore_and_owned_cleanup(self):
        for backend in ('vllm','sglang'):
            if backend=='sglang':self.c=Coordinator();self.d=Driver();self.http=HTTP()
            t,r=self.execute(backend)
            self.assertEqual(r['status'],'COMPLETED',r)
            self.assertEqual(r['quality'],'ACK_ONLY_PASS')
            self.assertEqual(self.http.posts,1);self.assertEqual(self.http.body['max_tokens'],64)
            self.assertEqual(self.http.body['seed'],42)
            self.assertEqual(self.http.body['messages'][0]['content'],'COMMON POLICY FIXTURE')
            self.assertEqual(self.c.events[0],'guard');self.assertEqual(self.c.events[1],'lock');self.assertEqual(self.c.events[-1],'unlock')
            self.assertEqual(self.c.events.count('restore'),1)
            self.assertLess(self.c.events.index('unload'),self.c.events.index('restore'))
            self.assertIn('stop',self.d.events);self.assertIn('remove',self.d.events)
            self.assertLess(self.d.events.index('stop'),self.d.events.index('logs'))
            self.assertLess(self.d.events.index('logs'),self.d.events.index('remove'))
            self.assertTrue((t.run/'server-log-tail.json').is_file())
            self.assertIsNone(self.d.row)
            self.assertEqual(self.http.post_thread,threading.get_ident())
    def test_docker_client_timeout_is_not_container_stop(self):
        self.d.mode='stop_timeout';t,r=self.execute()
        self.assertTrue(r['cleanup_confirmed']);self.assertIn('kill',self.d.events)
        self.assertLess(self.d.events.index('kill'),self.d.events.index('remove'))
    def test_identity_mismatch_signals_nothing_and_blocks_restore(self):
        self.d.mode='foreign_token';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('start',self.d.events)
        self.assertNotIn('stop',self.d.events);self.assertNotIn('kill',self.d.events);self.assertNotIn('remove',self.d.events)
        self.assertNotIn('restore',self.c.events);self.assertEqual(self.http.posts,0)
    def test_unlimited_swap_is_refused_before_start(self):
        self.d.mode='memory_swap_unlimited';t,r=self.execute()
        self.assertEqual(r['status'],'FAILED');self.assertNotIn('start',self.d.events)
        self.assertIn('restore',self.c.events);self.assertEqual(self.http.posts,0)
    def test_inherited_healthcheck_is_refused_before_start(self):
        self.d.mode='unexpected_healthcheck';t,r=self.execute()
        self.assertEqual(r['status'],'FAILED');self.assertNotIn('start',self.d.events)
        self.assertEqual(self.http.posts,0);self.assertIn('restore',self.c.events)
    def test_unknown_create_absence_is_not_accepted_as_recovered(self):
        self.d.mode='create_unknown_absent';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertFalse(r['cleanup_confirmed'])
        self.assertNotIn('restore',self.c.events);self.assertEqual(self.d.events.count('create'),1)
    def test_unknown_start_is_not_reissued_and_cleanup_proves_removal(self):
        self.d.mode='start_unknown';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.d.events.count('start'),1)
        self.assertTrue(r['cleanup_confirmed']);self.assertIn('restore',self.c.events);self.assertEqual(self.http.posts,0)
    def test_post_unknown_is_never_resent_and_marks_common_uncertain(self):
        self.http.mode='post_unknown';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.http.posts,1)
        self.assertIn('restore',self.c.events);self.assertTrue(any(x.startswith('uncertain:') for x in self.c.events))
    def test_startup_timeout_has_zero_post_and_restores(self):
        self.http.mode='not_ready';t,r=self.execute()
        self.assertEqual(r['status'],'FAILED');self.assertEqual(self.http.posts,0);self.assertIn('restore',self.c.events)
        self.assertGreaterEqual(self.clock.n,90)
    def test_survivor_blocks_restore(self):
        self.d.mode='survivor';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
        self.assertNotIn('remove',self.d.events)
    def test_remove_unknown_and_still_present_blocks_restore(self):
        self.d.mode='remove_unknown_present';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
    def test_resource_start_floor_no_unload(self):
        t,r=self.execute(probe=lambda:{**healthy(),'mem_available':23*h.GIB})
        self.assertNotIn('unload',self.c.events);self.assertEqual(self.http.posts,0)
    def test_resource_continue_floor_and_swap_growth_stop_owned(self):
        for key,value in [('mem_available',16*h.GIB),('mem_available',15*h.GIB),('swap_used',1),('gpu_used',59*h.GIB)]:
            self.c=Coordinator();self.d=Driver();self.http=HTTP()
            def probe():return {**healthy(),**({key:value} if 'start' in self.d.events else {})}
            t,r=self.execute(probe=probe)
            self.assertEqual(r['status'],'FAILED');self.assertEqual(self.http.posts,0);self.assertIn('stop',self.d.events)
            self.assertIn('restore',self.c.events)
    def test_bad_hash_and_noninternal_network_do_not_unload(self):
        def bad(_,**kw):raise assets.Blocked('SHA')
        t,r=self.execute(verify=bad)
        self.assertNotIn('unload',self.c.events);self.assertNotIn('create',self.d.events)
        self.c=Coordinator();self.d.mode='network_external'
        t,r=self.execute()
        self.assertNotIn('unload',self.c.events)
    def test_restore_is_one_attempt_and_unknown_on_failure(self):
        self.c.restore_fails=True;t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.c.events.count('restore'),1)
    def test_wrong_ack_is_not_general_quality_pass(self):
        self.http.mode='bad_ack';t,r=self.execute()
        self.assertEqual(r['environment'],'PASS');self.assertEqual(r['quality'],'ACK_FORMAT_FAIL')
    def test_context4096_and_fixed_model_no_trust_or_arbitrary_backend(self):
        for backend,flag in [('vllm','--max-model-len'),('sglang','--context-length')]:
            args=h.server_argv(backend)
            self.assertEqual(args[args.index(flag)+1],'4096');self.assertNotIn('--trust-remote-code',args)
        with self.assertRaises(h.Blocked):h.server_argv('arbitrary')
    def test_cli_human_guard_blocks_before_docker_or_coordinator(self):
        with patch.object(sys,'argv',['host_api_trial.py','--run-human-approved','--backend','vllm']),patch('host_api_trial.sys.stdin.isatty',return_value=False),patch('host_api_trial.helpers') as helper:
            with self.assertRaises(h.Blocked):h.main()
            helper.assert_not_called()
    def test_cli_repeated_operator_is_refused_before_model_or_source_work(self):
        root=Path(self.r['project_root'])/'agents/local_llm/.runtime/backend-api-trials';root.mkdir(parents=True)
        h.reserve_approved_attempt(root,'vllm','a'*64,root/'prior')
        def private(path):Path(path).mkdir(parents=True,exist_ok=True);return Path(path)
        argv=['host_api_trial.py','--run-human-approved','--backend','vllm','--operator-json','unused','--operator-sha256','a'*64]
        with patch.object(sys,'argv',argv),patch('host_api_trial.sys.stdin.isatty',return_value=True),patch.object(h,'install_sigterm_handler'),patch.object(h,'operator_record',return_value=self.r),patch.object(h,'helpers',return_value=(lambda *a:self.c,private,write,healthy)),patch.object(h,'Trial',side_effect=AssertionError('no trial work')):
            with self.assertRaisesRegex(h.Blocked,'ALREADY_RESERVED'):h.main()
    def test_post_resource_abort_is_unknown_and_never_late_or_resent(self):
        self.http.mode='wait_for_resource_abort'
        def probe():return {**healthy(),**({'mem_available':15*h.GIB} if self.http.posts else {})}
        t,r=self.execute(probe=probe)
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.http.posts,1)
        self.assertEqual(self.http.post_thread,threading.get_ident())
        self.assertTrue(any(x.startswith('uncertain:') for x in self.c.events))
        self.assertIn('restore',self.c.events)
    def test_startup_http_wait_is_monitored_without_any_post(self):
        self.http.mode='wait_for_startup_resource_abort'
        def probe():return {**healthy(),**({'mem_available':16*h.GIB} if self.http.gets else {})}
        t,r=self.execute(probe=probe)
        self.assertEqual(r['status'],'FAILED');self.assertEqual(self.http.posts,0)
        self.assertTrue(self.http.aborted.is_set());self.assertIn('restore',self.c.events)
        self.assertIsNone(self.d.monitor)
    def test_slow_startup_body_is_aborted_at_start_deadline_not_whole_budget(self):
        prior=self.http.request
        def slow(method,*args,**kwargs):
            if method=='GET':
                self.clock.n=91
                self.assertTrue(self.http.aborted.wait(1),'startup deadline monitor failed to abort')
                raise TimeoutError('fixture slow body')
            return prior(method,*args,**kwargs)
        self.http.request=slow;t,r=self.execute()
        self.assertEqual(r['status'],'FAILED');self.assertEqual(self.http.posts,0)
        self.assertIn('restore',self.c.events);self.assertLess(self.clock.n,100)
    def test_cleanup_disables_startup_rpc_pressure_callback(self):
        prior=self.d.stop
        def stop(*args,**kwargs):
            self.assertIsNone(self.d.monitor)
            return prior(*args,**kwargs)
        self.d.stop=stop;t,r=self.execute()
        self.assertEqual(r['status'],'COMPLETED');self.assertIn('restore',self.c.events)
    def test_unavailable_terminal_logs_do_not_prevent_cleanup_or_restore(self):
        def no_logs(*args,**kwargs):raise h.Unknown('fixture log read unavailable')
        self.d.logs=no_logs;t,r=self.execute()
        self.assertEqual(r['status'],'COMPLETED');self.assertTrue(r['cleanup_confirmed'])
        self.assertIn('remove',self.d.events);self.assertIn('restore',self.c.events)
    def test_entrypoint_start_time_counts_preflight_against_whole_budget(self):
        t,r=self.execute(start_time=-720)
        self.assertEqual(t.start_time,-720);self.assertNotIn('unload',self.c.events)
        self.assertEqual(self.http.posts,0)
    def test_failed_readonly_preflight_does_not_consume_model_start_attempt(self):
        reservations=[]
        def bad_hash(*args,**kwargs):raise h.Blocked('fixture hash mismatch')
        t,r=self.execute(verify=bad_hash,reserve=lambda:reservations.append('reserved'))
        self.assertEqual(reservations,[]);self.assertNotIn('unload',self.c.events)
    def test_one_attempt_is_reserved_before_unload_and_second_cannot_start(self):
        def reserve():
            self.assertNotIn('unload',self.c.events)
            return h.reserve_approved_attempt(self.root,'vllm','a'*64,self.root/'fixedrun')
        t,r=self.execute(reserve=reserve);self.assertEqual(r['status'],'COMPLETED')
        self.c=Coordinator();self.d=Driver();self.http=HTTP()
        t,r=self.execute(reserve=reserve)
        self.assertEqual(r['status'],'FAILED');self.assertNotIn('unload',self.c.events)
        self.assertEqual(self.http.posts,0)
    def test_sigterm_during_create_keeps_unknown_absence_and_no_restore(self):
        self.d.mode='create_sigterm_absent';t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertFalse(r['cleanup_confirmed'])
        self.assertNotIn('restore',self.c.events);self.assertEqual(self.d.events.count('create'),1)
    def test_sigterm_handler_is_explicitly_installed(self):
        with patch('fixed_trial_assets.signal.signal') as signal:
            assets.install_sigterm_handler();self.assertEqual(signal.call_args.args[1],assets.on_terminate)
        with self.assertRaises(KeyboardInterrupt):assets.on_terminate(15,None)
    def test_slow_hash_checks_deadline_before_any_unload(self):
        def slow(_,check):self.clock.n=716;check();return []
        t,r=self.execute(verify=slow)
        self.assertNotIn('unload',self.c.events);self.assertNotIn('image',self.d.events)
        self.assertEqual(self.http.posts,0)
    def test_image_volume_rejected_before_unload(self):
        self.d.mode='anonymous_volume';t,r=self.execute()
        self.assertNotIn('unload',self.c.events);self.assertNotIn('create',self.d.events)
    def test_missing_gpu_is_readonly_failure_before_unload_or_attempt(self):
        self.d.mode='missing_gpu';reservations=[]
        t,r=self.execute(reserve=lambda:reservations.append('reserved'))
        self.assertEqual(r['status'],'FAILED');self.assertEqual(reservations,[])
        self.assertNotIn('unload',self.c.events);self.assertNotIn('create',self.d.events)
    def test_late_ready_after_startup90_never_sends_post(self):
        original=self.http.request
        def late(method,*args,**kwargs):
            answer=original(method,*args,**kwargs)
            if method=='GET':self.clock.n+=91
            return answer
        self.http.request=late;t,r=self.execute()
        self.assertEqual(r['status'],'FAILED');self.assertEqual(self.http.posts,0)
        self.assertIn('restore',self.c.events)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.scope=patch.object(assets,'FIXED_PROJECT_ROOT',self.root/'project');self.scope.start()
    def tearDown(self):self.scope.stop();self.temp.cleanup()
    def tiny(self,data=b'data'):
        row={'name':'config.json','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        return {'repo':'cyankiwi/Qwen3-Coder-Next-AWQ-4bit','revision':'c92cabfad08cadb011dc169cabb3e6da621b0719','required_files':[row],'required_bytes':len(data)},row
    def opener(self,data):
        class Response(io.BytesIO):status=200;headers={}
        class Opener:
            calls=0
            def open(self,*args,**kwargs):self.calls+=1;return Response(data)
        return Opener()
    def test_manifest_all20_sha256_and_exact_bytes(self):
        d=assets.manifest();self.assertEqual(len(d['required_files']),20)
        self.assertEqual(sum(r['bytes'] for r in d['required_files']),48278252061)
        self.assertTrue(all(len(r['sha256'])==64 for r in d['required_files']))
    def test_stream_hash_success_and_overwrite_or_partial_no_request(self):
        d,row=self.tiny();opener=self.opener(b'data');target=self.root/'config.json'
        with patch.object(acquire,'manifest',return_value=d):
            self.assertEqual(acquire.fetch_one(row,target,opener,10**20)['bytes'],4)
            with self.assertRaises(assets.Blocked):acquire.fetch_one(row,target,opener,10**20)
        self.assertEqual(opener.calls,1)
        target.unlink();target.with_name('config.json.partial').write_bytes(b'partial')
        with patch.object(acquire,'manifest',return_value=d):
            with self.assertRaises(assets.Blocked):acquire.fetch_one(row,target,opener,10**20)
        self.assertEqual(opener.calls,1)
    def test_hash_failure_retains_partial_and_no_final_or_retry(self):
        d,row=self.tiny();opener=self.opener(b'evil');target=self.root/'config.json'
        with patch.object(acquire,'manifest',return_value=d):
            with self.assertRaises(assets.Blocked):acquire.fetch_one(row,target,opener,10**20)
            with self.assertRaises(assets.Blocked):acquire.fetch_one(row,target,opener,10**20)
        self.assertEqual(opener.calls,1);self.assertFalse(target.exists());self.assertTrue((self.root/'config.json.partial').exists())
    def test_redirect_and_new_target_are_fixed(self):
        for url in ['http://huggingface.co/x','https://evil.test/x','https://huggingface.co@evil.test/x','https://huggingface.co:444/x']:
            with self.assertRaises(assets.Blocked):acquire.allowed(url)
        acquire.allowed('https://us.aws.cdn.hf.co/reviewed-signed-path')
    def test_private_operator_digest_ack_and_bootstrap(self):
        d=record(self.root);path=self.root/'operator.json';raw=json.dumps(d).encode();path.write_bytes(raw);path.chmod(0o600)
        digest=hashlib.sha256(raw).hexdigest()
        self.assertEqual(assets.operator_record(path,digest)['model_dir'],d['model_dir'])
        with self.assertRaises(assets.Blocked):assets.operator_record(path,'0'*64)
        path.chmod(0o644)
        with self.assertRaises(assets.Blocked):assets.operator_record(path,digest)
        path.chmod(0o600);d['runtimes']['sglang']['bootstrap_complete_reviewed']=False
        raw=json.dumps(d).encode();path.write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(assets.Blocked):assets.operator_record(path,digest)
        self.assertEqual(assets.operator_record(path,digest,purpose='acquire')['model_dir'],d['model_dir'])
        self.assertEqual(assets.operator_record(path,digest,backend='vllm')['model_dir'],d['model_dir'])
    def test_placeholder_and_out_of_range_versions_are_rejected(self):
        d=record(self.root);path=self.root/'operator.json'
        for value in ['<VERIFIED_INSTALLED_VERSION>','reviewed','5.20.0','5.15.9']:
            d['runtimes']['vllm']['dependency_versions']['transformers']=value
            raw=json.dumps(d).encode();path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(assets.Blocked):assets.operator_record(path,hashlib.sha256(raw).hexdigest(),backend='vllm')
    def test_guard_rejection_precedes_acquisition_lock_or_network(self):
        d=record(self.root);d['model_dir']=str(self.root/'never-created')
        with self.assertRaises(assets.Blocked):
            acquire.acquire(d,lambda:(_ for _ in ()).throw(assets.Blocked('HOST_CONTEXT')),write,opener=self.opener(b''))
        self.assertFalse(Path(d['model_dir']).exists())

    def test_foreign_project_cannot_select_another_helper_source(self):
        d=record(self.root/'foreign');path=self.root/'operator.json';raw=json.dumps(d).encode();path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaisesRegex(assets.Blocked,'FIXED_INSTALLED_PROJECT'):assets.operator_record(path,hashlib.sha256(raw).hexdigest(),purpose='acquire')
    def test_acquisition_releases_resident_generation_lock_before_download(self):
        d=record(self.root);coordinator=Coordinator();coordinator.is_locked=False
        @contextmanager
        def locked():
            coordinator.is_locked=True
            try:yield
            finally:coordinator.is_locked=False
        coordinator.locked=locked
        def transfer(*a,**kw):
            self.assertFalse(coordinator.is_locked)
            return {'status':'FIXTURE_NO_NETWORK'}
        argv=['acquire_next_host.py','--acquire-human-approved','--operator-json','/fixture','--operator-sha256','a'*64]
        with patch.object(sys,'argv',argv),patch('acquire_next_host.sys.stdin.isatty',return_value=True),patch('acquire_next_host.install_sigterm_handler'),patch('acquire_next_host.operator_record',return_value=d),patch('acquire_next_host.helpers',return_value=(lambda *a:coordinator,None,write,None)),patch('acquire_next_host.acquire',side_effect=transfer),redirect_stdout(io.StringIO()):
            self.assertEqual(acquire.main(),0)


class TransportTests(unittest.TestCase):
    def test_http_abort_retains_raw_socket_when_connection_will_close(self):
        class Socket:
            shutdown_called=False;closed=False
            def shutdown(self,*args):self.shutdown_called=True
            def close(self):self.closed=True
        class Connection:
            sock=None;closed=False
            def close(self):self.closed=True
        client=h.LocalHTTP();raw=Socket();connection=Connection()
        client.connection=connection;client.active_socket=raw
        client.abort()
        self.assertTrue(raw.shutdown_called);self.assertTrue(raw.closed);self.assertTrue(connection.closed)
    def test_docker_spawn_interruption_without_handle_is_unknown_not_reaped(self):
        driver=h.Docker(lambda:None)
        with patch('host_api_trial.subprocess.Popen',side_effect=KeyboardInterrupt('fixture')):
            with self.assertRaisesRegex(h.Unknown,'NO_HANDLE'):driver.command(['FIXTURE_NOT_EXECUTED'])
        self.assertFalse(driver.clients_reaped)
    def test_approved_operator_digest_can_reserve_exactly_one_attempt(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);p=h.reserve_approved_attempt(root,'vllm','a'*64,root/'run')
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(p.read_text())['generation_request_limit'],1)
            with self.assertRaises(FileExistsError):h.reserve_approved_attempt(root,'vllm','a'*64,root/'second')
            with self.assertRaises(h.Blocked):h.reserve_approved_attempt(root,'../other','a'*64,root/'run')
    def test_fixed_create_disables_image_healthcheck_and_keeps_private_ipc(self):
        with tempfile.TemporaryDirectory() as name:
            r=record(Path(name));driver=h.Docker(lambda:None)
            with patch.object(driver,'command',return_value='a'*64) as command,patch('host_api_trial.os.stat',return_value=SimpleNamespace(st_gid=1234)),patch('host_api_trial.os.getgroups',return_value=[1234]):
                driver.create({'name':'fixture','token':'fixture','owner':'fixture'},r,'vllm')
            args=command.call_args.args[0]
            self.assertIn('--no-healthcheck',args);self.assertEqual(args[args.index('--ipc')+1],'private')
            self.assertEqual(args[args.index('--entrypoint')+1],'vllm')
    def test_docker_rpc_timeout_poll_checks_pressure_and_reaps_client(self):
        class Pipe:
            def close(self):pass
        class Process:
            def __init__(self):self.stdout=Pipe();self.stderr=Pipe();self.killed=False;self.reaped=False;self.polls=0
            def communicate(self,**kwargs):
                self.polls+=1
                raise h.subprocess.TimeoutExpired('fixture',kwargs['timeout'])
            def kill(self):self.killed=True
            def wait(self,**kwargs):self.reaped=True
        proc=Process();driver=h.Docker(lambda:None);calls=[]
        def monitor():
            calls.append(1)
            if len(calls)>=3:raise h.Blocked('fixture resource pressure')
        driver.monitor=monitor
        with patch('host_api_trial.subprocess.Popen',return_value=proc):
            with self.assertRaises(h.Unknown):driver.command(['FIXTURE_NOT_EXECUTED'])
        self.assertEqual(proc.polls,1);self.assertTrue(proc.killed);self.assertTrue(proc.reaped)
    def test_abort_between_connect_and_send_never_reconnects_or_posts(self):
        client=h.LocalHTTP();route={'ipv4':'172.29.0.7'}
        client.bind_route(route,lambda:route);client.arm()
        base=h.http.client.HTTPConnection
        class Socket:
            def settimeout(self,value):client.abort()
            def shutdown(self,*args):pass
            def close(self):pass
            def sendall(self,data):sends.append(data)
        connects=[];sends=[]
        class Connection(base):
            def connect(self):connects.append(1);self.sock=Socket()
        with patch('host_api_trial.http.client.HTTPConnection',Connection):
            with self.assertRaises(h.http.client.NotConnected):
                client.request('POST','/v1/chat/completions',{'fixed':'fixture'})
        self.assertEqual(len(connects),1);self.assertEqual(sends,[])
        self.assertTrue(client.aborted.is_set())
    def test_docker_client_interrupt_is_killed_reaped_and_unknown(self):
        class Pipe:
            def close(self):pass
        class Process:
            def __init__(self):self.stdout=Pipe();self.stderr=Pipe();self.killed=False;self.reaped=False
            def communicate(self,**kw):raise KeyboardInterrupt('fixture')
            def kill(self):self.killed=True
            def wait(self,**kw):self.reaped=True
        proc=Process();driver=h.Docker(lambda:None)
        with patch('host_api_trial.subprocess.Popen',return_value=proc):
            with self.assertRaises(h.Unknown):driver.command(['FIXTURE_NOT_EXECUTED'])
        self.assertTrue(proc.killed);self.assertTrue(proc.reaped);self.assertTrue(driver.clients_reaped)


if __name__=='__main__':unittest.main()
