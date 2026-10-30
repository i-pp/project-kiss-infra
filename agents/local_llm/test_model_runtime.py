import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
import model_runtime as runtime
from local_llm import Client,LocalError,GIB

SAFE={'available_bytes':40*GIB,'gpu_used_bytes':21*GIB,'swap_used_bytes':0}
POLICY=lambda task:{'system':'full fixture policy','metadata':{'version':'fixture','sha256':'fixture'}}

class Api:
    def __init__(self):
        self.states={v:('loaded' if k=='qwen-coder-30b' else 'unloaded') for k,v in runtime.PROFILES.items()}
        self.calls=[];self.busy=False;self.fail_load=False;self.fail_generation=False
        self.wait=False;self.abort_event=threading.Event()
    def request(self,method,path,payload=None,timeout=5):
        self.calls.append((method,path,payload,timeout));base=urlsplit(path).path
        if base=='/health':return {'status':'ok'}
        if base=='/models':return {'data':[{'id':k,'status':{'value':v}} for k,v in self.states.items()]}
        if base=='/v1/models':return {'data':[{'id':k} for k in self.states]}
        if base=='/slots':return [{'is_processing':self.busy}]
        if base=='/props':
            model=parse_qs(urlsplit(path).query).get('model',[runtime.PROFILES['qwen-coder-30b']])[0]
            return {'model_alias':model,'default_generation_settings':{'n_ctx':32768},'total_slots':1}
        if method=='POST':
            model=payload['model']
            if self.wait:
                self.abort_event.wait(1);raise LocalError('TRANSPORT_ERROR','aborted fixture')
            if base=='/models/load':
                assert not any(v=='loaded' for v in self.states.values())
                self.states[model]='loaded'
                if self.fail_load:raise LocalError('TRANSPORT_ERROR','ambiguous fixture load')
            elif base=='/models/unload':self.states[model]='unloaded'
            elif base=='/v1/chat/completions':
                if self.fail_generation:raise LocalError('TRANSPORT_ERROR','ambiguous fixture inference')
                return {'model':model,'choices':[{'message':{'content':'fixture advice','reasoning_content':'not exported'},'finish_reason':'stop'}]}
            else:raise AssertionError('Unexpected POST')
            return {'success':True}
        raise AssertionError('Unexpected HTTP')
    def abort(self):self.abort_event.set()
    def posts(self):return [(p,b['model']) for m,p,b,t in self.calls if m=='POST']

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'state'
        self.api=Api()
        def client_factory(**kwargs):
            kwargs.setdefault('api',self.api)
            return Client(**kwargs)
        self.r=runtime.Runtime(api=self.api,probe=lambda:SAFE,runtime=self.root,
            policy_provider=POLICY,client_factory=client_factory,confirmation=lambda:True,
            interval=.001,api_factory=lambda:self.api)
    def tearDown(self):self.temp.cleanup()
    def test_pending_human_deployment_blocks_every_mutation(self):
        self.r.confirmation=lambda:False
        for op in [lambda:self.r.prepare('gpt-oss-120b'),lambda:self.r.generate('qwen-coder-next','draft','x')]:
            with self.assertRaises(LocalError) as caught:op()
            self.assertEqual(caught.exception.code,'ROUTER_DEPLOYMENT_PENDING')
        self.assertEqual(self.api.calls,[])
    def test_unload_then_load_one_model_without_generation(self):
        result=self.r.prepare('gpt-oss-120b')
        self.assertEqual(self.api.posts(),[('/models/unload',runtime.PROFILES['qwen-coder-30b']),('/models/load',runtime.PROFILES['gpt-oss-120b'])])
        self.assertEqual(result['status'],'READY');self.assertEqual(result['generation_requests'],0)
        self.assertEqual(sum(v=='loaded' for v in self.api.states.values()),1)
    def test_restore30b_and_never_co_load_next(self):
        self.r.prepare('gpt-oss-120b');self.r.prepare('qwen-coder-next');result=self.r.prepare('qwen-coder-30b')
        self.assertEqual(result['model'],runtime.PROFILES['qwen-coder-30b'])
        self.assertEqual(sum(v=='loaded' for v in self.api.states.values()),1)
    def test_already_loaded_prepare_has_no_post(self):
        result=self.r.prepare('qwen-coder-30b');self.assertTrue(result['already_loaded']);self.assertFalse(self.api.posts())
    def test_busy_existing_request_prevents_unload(self):
        self.api.busy=True
        with self.assertRaises(LocalError) as caught:self.r.prepare('gpt-oss-120b')
        self.assertEqual(caught.exception.code,'BUSY');self.assertFalse(self.api.posts())
    def test_unknown_catalog_prevents_mutation(self):
        self.api.states['unapproved']='unloaded'
        with self.assertRaises(LocalError):self.r.prepare('gpt-oss-120b')
        self.assertFalse(self.api.posts())
    def test_two_loaded_models_are_rejected(self):
        self.api.states[runtime.PROFILES['gpt-oss-120b']]='loaded'
        with self.assertRaises(LocalError):self.r.prepare('qwen-coder-next')
        self.assertFalse(self.api.posts())
    def test_policy_failure_prevents_even_backend_reads(self):
        self.r.policy_provider=lambda task:(_ for _ in ()).throw(LocalError('POLICY_UNAVAILABLE','fixture'))
        with self.assertRaises(LocalError):self.r.prepare('gpt-oss-120b')
        self.assertFalse(self.api.calls)
    def test_preflight_pressure_prevents_unload(self):
        self.r.probe=lambda:{**SAFE,'available_bytes':23*GIB}
        with self.assertRaises(LocalError):self.r.prepare('gpt-oss-120b')
        self.assertFalse(self.api.calls)
    def test_ambiguous_load_is_not_retried_and_target_is_cleaned(self):
        self.api.fail_load=True
        with self.assertRaises(LocalError):self.r.prepare('gpt-oss-120b')
        self.assertEqual(sum(p=='/models/load' for p,m in self.api.posts()),1)
        self.assertEqual(self.api.states[runtime.PROFILES['gpt-oss-120b']],'unloaded')
        self.assertTrue((self.root/'UNCERTAIN.json').exists())
        before=list(self.api.calls)
        with self.assertRaises(LocalError):self.r.prepare('qwen-coder-next')
        self.assertEqual(before,self.api.calls)
    def test_selected_generation_never_loads_an_unloaded_model(self):
        with self.assertRaises(LocalError) as caught:self.r.generate('gpt-oss-120b','draft','fixture')
        self.assertEqual(caught.exception.code,'MODEL_NOT_LOADED');self.assertFalse(self.api.posts())
    def test_busy_selected_model_never_receives_generation(self):
        self.api.busy=True
        with self.assertRaises(LocalError) as caught:self.r.generate('qwen-coder-30b','draft','fixture')
        self.assertEqual(caught.exception.code,'BUSY');self.assertFalse(self.api.posts())
    def test_selected_generation_reuses_policy_and_not_executed_contract(self):
        self.r.prepare('gpt-oss-120b');self.api.calls=[]
        result=self.r.generate('gpt-oss-120b','review','fixture',32)
        post=next(c for c in self.api.calls if c[0]=='POST')
        self.assertEqual(post[1],'/v1/chat/completions?autoload=false')
        self.assertEqual(post[2]['messages'][0]['content'],'full fixture policy')
        self.assertEqual(post[2]['model'],runtime.PROFILES['gpt-oss-120b'])
        self.assertLessEqual(post[3],218)
        self.assertEqual(result['verification_status'],'NOT_EXECUTED');self.assertFalse(result['code_executed'])
        self.assertNotIn('not exported',json.dumps(result))
    def test_generation_failure_unloads_only_its_model_and_blocks_retry(self):
        self.r.prepare('qwen-coder-next');self.api.calls=[];self.api.fail_generation=True
        with self.assertRaises(LocalError):self.r.generate('qwen-coder-next','draft','fixture')
        self.assertEqual(self.api.posts(),[('/v1/chat/completions?autoload=false',runtime.PROFILES['qwen-coder-next']),('/models/unload',runtime.PROFILES['qwen-coder-next'])])
        self.assertTrue((self.root/'UNCERTAIN.json').exists())
    def test_lifecycle_pressure_aborts_own_http_connection(self):
        self.api.wait=True;self.r.probe=lambda:{**SAFE,'available_bytes':15*GIB}
        with self.assertRaises(LocalError) as caught:self.r._post('/models/load',runtime.PROFILES['gpt-oss-120b'],time.monotonic()+.1)
        self.assertEqual(caught.exception.code,'RESOURCE_LIMIT');self.assertTrue(self.api.abort_event.is_set())
        self.assertEqual(len(self.api.posts()),1)
    def test_lifecycle_deadline_never_resends(self):
        self.api.wait=True
        with self.assertRaises(LocalError):self.r._post('/models/load',runtime.PROFILES['gpt-oss-120b'],time.monotonic()+.01)
        self.assertEqual(len(self.api.posts()),1);self.assertTrue(self.api.abort_event.is_set())
    def test_confirmation_rejects_weak_or_unverified_deployment(self):
        with self.assertRaises(LocalError):runtime.confirm_deployment({'image':runtime.IMAGE,'container_id':'a'*64,'contract':{}},runtime=self.root)
        self.assertFalse(self.api.calls);self.assertFalse((self.root/'router-deployment.json').exists())
    def test_confirmation_marker_is_owner_private_and_registry_bound(self):
        from test_endpoint_config import fixture
        self.r.confirmation=None;data=fixture(self.root)
        p=self.root/'router-deployment.json';data['registry_sha256']='wrong';p.write_text(json.dumps(data))
        self.assertFalse(self.r.confirmed())
        data['registry_sha256']=runtime.endpoint_config.digest(self.root)
        p.write_text(json.dumps(data));self.assertTrue(self.r.confirmed())
        p.chmod(0o644);self.assertFalse(self.r.confirmed())
    def test_status_is_get_only_and_does_not_claim_unloaded_ready(self):
        data=self.r.status('gpt-oss-120b');self.assertEqual(data['status'],'NOT_LOADED')
        self.assertFalse(self.api.posts())
    def test_file_lock_serializes_old_and_new_clients(self):
        with Client(runtime=self.root).locked():
            with self.assertRaises(LocalError) as caught:self.r.prepare('gpt-oss-120b')
        self.assertEqual(caught.exception.code,'BUSY');self.assertFalse(self.api.calls)
    def test_bad_profile_cannot_choose_arbitrary_command_or_url(self):
        for value in ['http://example.test','/models/unapproved.gguf',[],None]:
            with self.assertRaises(LocalError):self.r.prepare(value)
        self.assertFalse(self.api.calls)
    def test_private_route_sequence_and_legacy_client_share_one_verified_http_destination(self):
        from test_endpoint_config import fixture
        fixture(self.root)
        backend=Api();addresses=[]
        class Connection:
            sock=None
            def __init__(conn,host,port,timeout):addresses.append((host,port));conn.timeout=timeout
            def request(conn,method,path,body=None,headers=None):conn.call=(method,path,json.loads(body) if body else None,conn.timeout)
            def getresponse(conn):
                class Response:
                    status=200
                    def read(response,limit):return json.dumps(backend.request(*conn.call)).encode()
                return Response()
            def close(conn):pass
        r=runtime.Runtime(runtime=self.root,probe=lambda:SAFE,policy_provider=POLICY,interval=.001)
        with patch('local_llm.http.client.HTTPConnection',Connection):
            for profile in ['gpt-oss-120b','qwen-coder-next','qwen-coder-30b']:
                r.prepare(profile)
                if profile!='qwen-coder-30b':
                    legacy=Client(runtime=self.root,probe=lambda:SAFE,policy_provider=POLICY)
                    previous=list(backend.posts())
                    with self.assertRaises(LocalError) as caught:legacy.generate('draft','fixture')
                    self.assertEqual(caught.exception.code,'MODEL_NOT_LOADED');self.assertEqual(previous,backend.posts())
                result=r.generate(profile,'draft','fixture',32)
                self.assertEqual(result['model'],runtime.PROFILES[profile])
        self.assertEqual(set(addresses),{('172.19.0.2',8080)})
        generated=[model for path,model in backend.posts() if path.startswith('/v1/chat/completions')]
        self.assertEqual(generated,[runtime.PROFILES[k] for k in ['gpt-oss-120b','qwen-coder-next','qwen-coder-30b']])
if __name__=='__main__':unittest.main()
