import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch
import host_router_maintenance as hm

CID='a'*64
NEW='b'*64
NET='c'*64
EP='f'*64

class Engine:
    def __init__(self,llm):
        self.llm=llm;self.calls=[];self.router=None;self.fail_create_unknown=False;self.publish_port=True
        self.extra_peer=False;self.wrong_network=False;self.route_ip='172.19.0.2'
        self.original={'Id':CID,'Name':hm.ORIGINAL,'Image':hm.IMAGE,'Config':{'Labels':{},'User':str(os.getuid())},'HostConfig':{},'State':{'Running':True}}
    def router_object(self,token):
        repo=self.llm.parents[1]
        return {'Id':NEW,'Name':'/'+hm.ROUTER,'Image':hm.IMAGE,'Path':'/app/llama-server','Args':hm.ROUTER_ARGS,
            'Config':{'Labels':{'com.docker.compose.project':hm.PROJECT,'io.aceis.deployment':token},'User':str(os.getuid())+':'+str(os.getgid())},
            'HostConfig':{'Memory':34359738368,'MemorySwap':34359738368,'NanoCpus':8000000000,'PidsLimit':512,'ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':None,'SecurityOpt':['no-new-privileges:true'],'PortBindings':{'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]}},
            'State':{'Running':False},'NetworkSettings':{'Networks':{'project-kiss-large-coder-b3_local':{'NetworkID':NET,'EndpointID':EP,'IPAddress':self.route_ip,'IPPrefixLen':16}}},
            'Mounts':[{'Type':'bind','Destination':k,'Source':str(v),'RW':rw} for k,v,rw in [('/models',repo/'models',False),('/cache',repo/'.cache/large-coder-b3/runtime',True),('/config/models.ini',self.llm/'integration/router-presets.PROPOSAL.ini',False)]]}
    def __call__(self,args,**kwargs):
        assert args[:3]==['/usr/bin/docker','--host','unix:///var/run/docker.sock']
        op=args[3:];self.calls.append(op)
        if op[0]=='inspect':
            obj=self.original if op[1]==CID else self.router
            return subprocess.CompletedProcess(args,0,json.dumps([obj]),'') if obj else subprocess.CompletedProcess(args,1,'','Error: No such object')
        if op[:2]==['network','inspect']:
            peers={}
            if self.router and self.router['State']['Running']:peers[NEW]={'EndpointID':EP,'IPv4Address':self.route_ip+'/16'}
            if self.extra_peer:peers['9'*64]={'EndpointID':'8'*64,'IPv4Address':'172.19.0.3/16'}
            network={'Name':hm.endpoint_config.NETWORK,'Id':'9'*64 if self.wrong_network else NET,
                     'Internal':True,'Driver':'bridge','Containers':peers,'IPAM':{'Config':[{'Subnet':'172.19.0.0/16'}]}}
            return subprocess.CompletedProcess(args,0,json.dumps([network]),'')
        if op[0]=='compose':
            if 'create' in op:
                assert self.router is None,'No duplicate creation'
                self.router=self.router_object(kwargs['env']['ROUTER_DEPLOYMENT_TOKEN'])
                if self.fail_create_unknown:
                    self.fail_create_unknown=False;raise subprocess.TimeoutExpired(args,1)
            return subprocess.CompletedProcess(args,0,'','')
        if op[0] in ['start','stop']:
            obj=self.original if op[-1]==CID else self.router
            assert obj is not None
            obj['State']['Running']=op[0]=='start'
            if obj is self.router:
                obj['NetworkSettings']['Ports']={'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]} if obj['State']['Running'] and self.publish_port else {}
            return subprocess.CompletedProcess(args,0,obj['Id'],'')
        raise AssertionError(op)
    def mutations(self):return [c for c in self.calls if c[0] in ['start','stop'] or (c[0]=='compose' and 'create' in c)]

class Fixture(hm.Maintenance):
    fail_router_gate=False
    def human_guard(self):self.enter('mock_human_host_guard')
    def device_check(self):self.env['GPU_GID']='1000'
    def idle_coordinator(self):self.enter('mock_coordinator_idle')
    def gate(self,mode):
        self.enter('readonly_'+mode+'_gate')
        if mode=='router' and self.fail_router_gate:raise hm.Failure('GATE_FAILED','fixture connection failed')
        if mode=='router':assert self.engine.router['State']['Running'] and not self.engine.original['State']['Running']
        else:assert self.engine.original['State']['Running']

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.llm=Path(self.temp.name)/'repo/agents/local_llm';self.root=self.llm/'.runtime';self.root.mkdir(parents=True,mode=0o700)
        (self.root/'generation.lock').touch(mode=0o600)
        profile={'project_root':str(self.llm.parents[1]),'orchestrator_root':'/public-fixture','image':hm.IMAGE,'router_name':hm.ROUTER,'resident_container_id':CID,
                 'existing_internal_network':hm.endpoint_config.NETWORK,'internal_network_id':NET}
        p=self.root/'router-host-profile.json';p.write_text(json.dumps(profile));p.chmod(0o600)
        (self.llm/'integration').mkdir()
        shutil.copyfile(Path(hm.__file__).with_name('router-presets.PROPOSAL.ini'),self.llm/'integration/router-presets.PROPOSAL.ini')
        (self.llm/'model_registry.json').write_text('{"fixture":"registry"}')
        self.engine=Engine(self.llm);self.tasks=[]
    def tearDown(self):
        for task in self.tasks:
            if not task.log.closed:task.close()
        self.temp.cleanup()
    def task(self):
        task=Fixture(self.llm,execute=self.engine);task.engine=self.engine;self.tasks.append(task);return task
    def run_main(self,mode,fail_gate=False):
        task=self.task();task.fail_router_gate=fail_gate
        with patch.object(hm,'Maintenance',return_value=task),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=hm.main([mode])
        return code,task
    def test_fresh_deploy_preserves_original_and_creates_once(self):
        code,t=self.run_main('deploy');self.assertEqual(code,0)
        self.assertFalse(self.engine.original['State']['Running']);self.assertTrue(self.engine.router['State']['Running'])
        self.assertEqual(t.state['resident_cid'],CID);self.assertEqual(t.state['phase'],'DEPLOYED')
        self.assertEqual(sum('create' in c for c in self.engine.calls),1)
    def test_gate_failure_rolls_back_original_and_records_exit(self):
        code,t=self.run_main('deploy',fail_gate=True);self.assertEqual(code,1)
        self.assertTrue(self.engine.original['State']['Running']);self.assertFalse(self.engine.router['State']['Running'])
        text=t.log_path.read_text();self.assertIn('readonly_router_gate',text);self.assertIn('"exit_code": 1',text)
        self.assertEqual(t.state['phase'],'ROLLED_BACK')
    def test_unrealized_port_rolls_back_before_http_gate(self):
        self.engine.publish_port=False
        code,t=self.run_main('deploy');self.assertEqual(code,1)
        self.assertTrue(self.engine.original['State']['Running']);self.assertFalse(self.engine.router['State']['Running'])
        log=t.log_path.read_text()
        self.assertIn('ROUTER_PORT_UNPUBLISHED',log)
        self.assertNotIn('"step": "readonly_router_gate"',log)
        self.assertEqual(sum('create' in c for c in self.engine.calls),1)
    def test_internal_route_uses_existing_container_and_publishes_bound_receipt(self):
        self.engine.publish_port=False
        code,t=self.run_main('deploy-internal');self.assertEqual(code,0)
        receipt=hm.endpoint_config.route(self.root)
        self.assertEqual(receipt['ipv4'],'172.19.0.2');self.assertEqual(receipt['container_id'],NEW)
        self.assertTrue(receipt['human_deployment_confirmed'])
        self.assertFalse((self.root/'router-candidate.json').exists())
        self.assertFalse(self.engine.original['State']['Running'])
        self.assertEqual(sum('create' in c for c in self.engine.calls),1)
        code,_=self.run_main('resume-internal');self.assertEqual(code,0)
        self.assertEqual(sum('create' in c for c in self.engine.calls),1)
    def test_internal_failure_retires_candidate_and_restores_localhost(self):
        self.engine.publish_port=False
        code,t=self.run_main('deploy-internal',fail_gate=True);self.assertEqual(code,1)
        self.assertTrue(self.engine.original['State']['Running']);self.assertFalse(self.engine.router['State']['Running'])
        self.assertEqual(hm.endpoint_config.route(self.root)['mode'],'resident')
        self.assertFalse((self.root/'router-deployment.json').exists())
        self.assertTrue(list(self.root.glob('router-candidate.json.retired-*')))
    def test_internal_rollback_retires_active_route_and_restores_resident(self):
        self.run_main('deploy-internal')
        code,t=self.run_main('rollback');self.assertEqual(code,0)
        self.assertEqual(hm.endpoint_config.route(self.root)['ipv4'],'127.0.0.1')
        self.assertTrue(list(self.root.glob('router-deployment.json.retired-*')))
        self.assertTrue(self.engine.original['State']['Running'])
    def test_unknown_peer_or_network_prevents_container_mutation(self):
        for attr in ['extra_peer','wrong_network']:
            setattr(self.engine,attr,True)
            code,t=self.run_main('resume-internal');self.assertNotEqual(code,0)
            self.assertIn('NETWORK_PEER_UNCONFIRMED' if attr=='extra_peer' else 'NETWORK_ID_MISMATCH',t.log_path.read_text())
            self.assertFalse(self.engine.mutations());setattr(self.engine,attr,False)
    def test_internal_public_ip_is_not_published_and_original_is_restored(self):
        self.engine.route_ip='8.8.8.8'
        code,t=self.run_main('deploy-internal');self.assertNotEqual(code,0)
        self.assertTrue(self.engine.original['State']['Running'])
        self.assertFalse((self.root/'router-deployment.json').exists())
    def test_internal_gate_has_no_endpoint_argument(self):
        task=self.task();task.internal_route=True
        def execute(args,**kwargs):
            self.assertEqual(args[-2:],['router','--candidate'])
            self.assertFalse(any('172.19' in x or 'http:' in x for x in args))
            return subprocess.CompletedProcess(args,0,'{}','')
        task.execute=execute;hm.Maintenance.gate(task,'router')
    def test_endpoint_change_after_get_gate_prevents_receipt_and_restores_original(self):
        task=self.task();original_gate=task.gate
        def gate(mode):
            original_gate(mode)
            if mode=='router':self.engine.router['NetworkSettings']['Networks'][hm.endpoint_config.NETWORK]['IPAddress']='172.19.0.3'
        task.gate=gate
        with patch.object(hm,'Maintenance',return_value=task),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=hm.main(['deploy-internal'])
        self.assertEqual(code,1);self.assertTrue(self.engine.original['State']['Running'])
        self.assertFalse((self.root/'router-deployment.json').exists())
    def test_unsafe_candidate_is_not_overwritten_or_used(self):
        p=self.root/'router-candidate.json';p.write_text('{}');p.chmod(0o600)
        code,task=self.run_main('deploy-internal')
        self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations());self.assertEqual(p.read_text(),'{}')
    def test_gate_failure_reports_endpoint_and_keeps_existing_deadline(self):
        task=self.task()
        def execute(args,**kwargs):
            self.assertEqual(kwargs['timeout'],100)
            return subprocess.CompletedProcess(args,1,json.dumps({'status':'BLOCKED','reason':'HTTP_TIMEOUT','endpoint':'/health','elapsed_seconds':90}), '')
        task.execute=execute
        with self.assertRaises(hm.Failure) as caught:hm.Maintenance.gate(task,'router')
        self.assertEqual(caught.exception.code,'READONLY_GATE_FAILED')
        self.assertIn('/health',str(caught.exception))
        self.assertIn('duration_seconds',task.log_path.read_text())
    def test_ambiguous_create_requires_explicit_resume_and_never_duplicates(self):
        self.engine.fail_create_unknown=True;code,t=self.run_main('deploy');self.assertEqual(code,124)
        self.assertTrue(self.engine.original['State']['Running']);self.assertIsNone(t.state['router_cid'])
        code,_=self.run_main('deploy');self.assertNotEqual(code,0)
        code,t=self.run_main('resume');self.assertEqual(code,0)
        self.assertEqual(sum('create' in c for c in self.engine.calls),1)
    def test_repeated_success_is_idempotent_without_restart(self):
        self.run_main('deploy');before=list(self.engine.mutations())
        code,_=self.run_main('deploy');self.assertEqual(code,0);self.assertEqual(before,self.engine.mutations())
    def test_explicit_rollback_stops_only_owned_router_and_starts_exact_original(self):
        self.run_main('deploy');code,t=self.run_main('rollback');self.assertEqual(code,0)
        self.assertTrue(self.engine.original['State']['Running']);self.assertFalse(self.engine.router['State']['Running'])
        self.assertFalse(any(c[0] in ['rm','prune','update'] for c in self.engine.calls))
    def test_unknown_existing_router_is_never_adopted_or_stopped(self):
        self.engine.router=self.engine.router_object('c'*32)
        code,_=self.run_main('deploy');self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations())
    def test_permission_denied_is_distinct_from_normal_not_found(self):
        task=self.task()
        task.execute=lambda args,**kw:subprocess.CompletedProcess(args,1,'','permission denied while trying to connect to the docker API at unix:///var/run/docker.sock')
        with self.assertRaises(hm.Failure) as caught:task.inspect(CID)
        self.assertEqual(caught.exception.code,'DOCKER_PERMISSION_DENIED')
        self.assertIn('permission denied',task.log_path.read_text())
        self.assertFalse(self.engine.mutations())
    def test_normal_missing_router_is_not_a_connection_error(self):
        task=self.task()
        self.assertIsNone(task.inspect(hm.ROUTER))
        task.execute=lambda args,**kw:subprocess.CompletedProcess(args,1,'','Error response from daemon: No such container: project-kiss-aceis-router')
        self.assertIsNone(task.inspect(hm.ROUTER))
        self.assertFalse(self.engine.mutations())
    def test_changed_original_identity_prevents_all_mutations(self):
        self.engine.original['Image']='unapproved'
        code,_=self.run_main('deploy');self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations())
    def test_legacy_cid_record_requires_reconciliation(self):
        (self.root/'router-host-maintenance.cid').write_text(NEW)
        code,_=self.run_main('deploy');self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations())
    def test_uncertain_inference_blocks_deploy_and_is_not_deleted(self):
        marker=self.root/'UNCERTAIN.json';marker.write_text('{}')
        code,_=self.run_main('deploy');self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations());self.assertTrue(marker.exists())
    def test_existing_healthy_original_rollback_needs_no_ownership_adoption(self):
        code,_=self.run_main('rollback');self.assertEqual(code,0);self.assertFalse(self.engine.mutations())
    def test_preset_cannot_redirect_to_unapproved_model(self):
        p=self.llm/'integration/router-presets.PROPOSAL.ini';p.write_text(p.read_text().replace('/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf','http://unapproved'))
        code,_=self.run_main('deploy');self.assertNotEqual(code,0);self.assertFalse(self.engine.mutations())
    def test_source_guard_preserves_parent_errexit_and_never_executes_python(self):
        for name in ['deploy_router.sh','rollback_router.sh']:
            path=Path(hm.__file__).with_name(name)
            script='set -eu; before=$-; source "$1"; test "$before" = "$-"; printf "PARENT_ALIVE\\n"'
            r=subprocess.run(['/bin/bash','-c',script,'fixture',str(path)],capture_output=True,text=True,timeout=3)
            self.assertEqual(r.returncode,0);self.assertIn('PARENT_ALIVE',r.stdout);self.assertIn('source',r.stderr)
    def test_child_failure_can_be_handled_without_closing_parent(self):
        path=Path(hm.__file__).with_name('deploy_router.sh')
        r=subprocess.run(['/bin/bash','-c','set -e; bash "$1" --invalid || printf "CHILD_ERROR_HANDLED\\n"; printf "PARENT_ALIVE\\n"','fixture',str(path)],capture_output=True,text=True,timeout=3)
        self.assertEqual(r.returncode,0);self.assertIn('PARENT_ALIVE',r.stdout)
if __name__=='__main__':unittest.main()
