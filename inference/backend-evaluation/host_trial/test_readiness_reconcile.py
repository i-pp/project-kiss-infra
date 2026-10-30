"""Private temporary fixtures only. No real Docker/API/model/marker operation."""
import base64
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import reconcile_vllm_readiness as r


def encoded(data):return (json.dumps(data,indent=2)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    raw=data if isinstance(data,bytes) else encoded(data)
    path.write_bytes(raw);path.chmod(0o600);return sha(raw)
def current():return {'models':dict(r.STATES),'health':{'status':'ok'},'properties':{'model_alias':r.MODEL,
    'default_generation_settings':{'n_ctx':32768},'total_slots':1},'slots':[{'is_processing':False}],
    'resources':{'available_bytes':32*(1<<30),'gpu_used_bytes':22*(1<<30),'swap_used_bytes':0}}


class Coordinator:
    def __init__(self):self.events=[];self.data=current();self.on_observe=None
    def guard(self):self.events.append('guard')
    def observe(self):
        self.events.append('observe')
        if self.on_observe:self.on_observe()
        return copy.deepcopy(self.data)


class Docker:
    def __init__(self):self.calls=[];self.present=False
    def absent(self,cid,name):
        self.calls.append((cid,name))
        if self.present:raise r.Blocked('present')
        return [{'id':cid,'name':name,'absent':True}]


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.repo=Path(self.tmp.name)/'repo'
        self.rt=self.repo/'agents/local_llm/.runtime';self.rt.mkdir(parents=True,mode=0o700)
        self.b={'schema':1,'run_name':'vllm-fixed-readiness-fixture','container_id':'a'*64,
                'container_name':'aceis-next-vllm-fixture','operator_name':'fixed-operator.json',
                'coordinator_runtime_relative':'.runtime/fixed-coordinator'}
        self.run=self.rt/'backend-api-trials'/self.b['run_name'];self.run.mkdir(parents=True,mode=0o700)
        write(self.rt/'generation.lock',b'')
        self.marker={'code':r.CODE,'time':123.5,'automatic_retry':False};self.original=encoded(self.marker)
        self.b['marker_sha256']=write(self.rt/'UNCERTAIN.json',self.original)
        op={'project_root':str(self.repo),'model_dir':str(self.repo/'models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c'),
            'coordinator_runtime_relative':self.b['coordinator_runtime_relative']}
        self.b['operator_sha256']=write(self.rt/self.b['operator_name'],op)
        self.b['profile_sha256']=write(self.rt/'router-host-profile.json',{'fixed':'fixture'})
        self.b['code_files']={'fixed_source.py':write(self.repo/'fixed_source.py',b'NOT EXECUTED FIXTURE')}
        summary={'status':'UNKNOWN','backend':'vllm','environment':'FAIL','quality':'UNASSESSED','generation_requests':0,
            'generation_request_intents':0,'generation_uncertain':False,'cleanup_confirmed':True,
            'source_metadata_unchanged':True,'automatic_retry':False,'code_executed':False,'reason':r.REASON,
            'restoration':{'status':'RESTORED','model_states':dict(r.STATES)}}
        files={'summary.json':summary,'identity.json':{'name':self.b['container_name'],'owner':str(os.getuid())},
            'temporary-route.json':{'container_id':self.b['container_id']},'server-log-tail.json':{'container_id':self.b['container_id'],'terminal_before_read':True},
            'event-start.json':{'event':'start_owned_intent','cid':self.b['container_id']},
            'event-terminal.json':{'event':'owned_container_terminal','cid':self.b['container_id'],'state':'exited'},
            'event-create.json':{'event':'create_owned_intent','name':self.b['container_name']}}
        self.b['run_files']={name:write(self.run/name,data) for name,data in files.items()}
        self.summary=(self.run/'summary.json').read_bytes()
        self.attempt=self.rt/'backend-api-trials'/('attempt-vllm-'+self.b['operator_sha256']+'.json')
        write(self.attempt,{'backend':'vllm','operator_sha256':self.b['operator_sha256'],'run':str(self.run),
            'attempt_limit':1,'generation_request_limit':1,'automatic_retry':False})
        self.c=Coordinator();self.d=Docker()
    def changed_run(self,name,mutate):
        data=json.loads((self.run/name).read_text());mutate(data);self.b['run_files'][name]=write(self.run/name,data)
    def assert_block_preserved(self):
        self.assertEqual((self.rt/'UNCERTAIN.json').read_bytes(),self.original)
        self.assertEqual((self.run/'summary.json').read_bytes(),self.summary)
        self.assertTrue(self.attempt.exists())
    def test_bindings_require_fixed_private_runtime_location(self):
        raw=encoded({'schema':1,'private_storage_fixture':True})
        scoped=patch.object(r,'BINDINGS_SHA',sha(raw));scoped.start();self.addCleanup(scoped.stop)
        binding_path=self.rt/r.BINDINGS_NAME
        with self.assertRaises((r.Blocked,FileNotFoundError)):
            r.load_bindings(self.repo)
        write(binding_path,raw)
        self.assertEqual(r.load_bindings(self.repo),json.loads(raw))
        binding_path.chmod(0o644)
        with self.assertRaises(r.Blocked):r.load_bindings(self.repo)
        self.assert_block_preserved()
    def test_success_archives_original_after_durable_audit_preserves_summary_and_consumed_attempt(self):
        def archive(source,dest):
            audit=json.loads((dest.parent/'audit.json').read_text())
            self.assertEqual(base64.b64decode(audit['original_marker_base64']),self.original)
            self.assertEqual(audit['original_marker_parsed'],self.marker)
            self.assertEqual(audit['summary_status_preserved'],'UNKNOWN')
            self.assertEqual(audit['status'],'ALL_READONLY_PROBES_PASSED_ARCHIVE_AUTHORIZED')
            self.assertFalse(audit['powerloss_rename_namespace_durability_guaranteed'])
            os.rename(source,dest)
        result=r.reconcile(self.repo,self.b,self.c,self.d,rename=archive)
        self.assertEqual(result['status'],'RECONCILED_READINESS_ONLY_NO_GENERATION')
        self.assertFalse((self.rt/'UNCERTAIN.json').exists())
        self.assertEqual(Path(result['archived_marker']).read_bytes(),self.original)
        self.assertEqual((self.run/'summary.json').read_bytes(),self.summary);self.assertTrue(self.attempt.exists())
        self.assertEqual(len(self.d.calls),2);self.assertEqual(self.c.events,['guard','observe'])
        self.assertEqual(Path(result['audit_directory']).stat().st_mode&0o777,0o700)
        self.assertEqual((Path(result['audit_directory'])/'audit.json').stat().st_mode&0o777,0o600)
    def test_busy_lock_preserves_marker_and_performs_no_docker_read(self):
        fd=os.open(self.rt/'generation.lock',os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(r.Blocked,'BUSY'):r.reconcile(self.repo,self.b,self.c,self.d)
        finally:os.close(fd)
        self.assert_block_preserved();self.assertEqual(self.d.calls,[])
    def test_unsafe_or_missing_lock_is_not_created_or_chmoded(self):
        lock=self.rt/'generation.lock';lock.chmod(0o644)
        with self.assertRaisesRegex(r.Blocked,'LOCK_UNSAFE'):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assertEqual(lock.stat().st_mode&0o777,0o644);self.assert_block_preserved()
        lock.unlink()
        with self.assertRaises(FileNotFoundError):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assertFalse(lock.exists());self.assert_block_preserved()
    def test_normal_host_guard_failure_preserves_marker(self):
        self.c.guard=lambda:(_ for _ in ()).throw(r.Blocked('HOST_CONTEXT_REQUIRED'))
        with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assert_block_preserved();self.assertEqual(self.d.calls,[])
    def test_summary_generation_uncertain_or_other_unknown_is_not_cleared(self):
        for field,value in [('generation_requests',1),('generation_request_intents',1),('generation_requests',False),('generation_uncertain',True),('reason','OTHER_UNKNOWN')]:
            old=(self.run/'summary.json').read_bytes();oldhash=self.b['run_files']['summary.json']
            self.changed_run('summary.json',lambda d:d.update({field:value}))
            with self.assertRaisesRegex(r.Blocked,'ZERO_POST'):r.reconcile(self.repo,self.b,self.c,self.d)
            write(self.run/'summary.json',old);self.b['run_files']['summary.json']=oldhash
        self.assert_block_preserved()
    def test_post_or_response_artifact_blocks_even_when_summary_zero(self):
        for name in ['request.json','post-intent.json','response.json']:
            p=self.run/name;write(p,{})
            with self.assertRaisesRegex(r.Blocked,'REQUEST_OR_POST'):r.reconcile(self.repo,self.b,self.c,self.d)
            p.unlink()
        self.assert_block_preserved()
    def test_wrong_route_or_log_or_start_cid_blocks(self):
        for name,key in [('temporary-route.json','container_id'),('server-log-tail.json','container_id'),('event-start.json','cid')]:
            old=(self.run/name).read_bytes();oldhash=self.b['run_files'][name]
            self.changed_run(name,lambda d:d.update({key:'b'*64}))
            with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
            write(self.run/name,old);self.b['run_files'][name]=oldhash
        self.assert_block_preserved()
    def test_operator_profile_source_or_marker_hash_mismatch_blocks(self):
        for path in [self.rt/self.b['operator_name'],self.rt/'router-host-profile.json',self.repo/'fixed_source.py',self.rt/'UNCERTAIN.json']:
            old=path.read_bytes();write(path,b'changed')
            with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
            write(path,old)
        self.assert_block_preserved()
    def test_present_container_or_name_blocks_before_health_and_archive(self):
        self.d.present=True
        with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assertNotIn('observe',self.c.events);self.assert_block_preserved()
    def test_busy_unhealthy_wrong_context_and_pressure_preserve_block(self):
        original=current()
        cases=[lambda d:d['health'].update(status='bad'),lambda d:d['properties']['default_generation_settings'].update(n_ctx=4096),
               lambda d:d.update(slots=[{'is_processing':True}]),lambda d:d['models'].update({'other':'loaded'}),
               lambda d:d['resources'].update(swap_used_bytes=1),lambda d:d['resources'].update(available_bytes=1)]
        for mutate in cases:
            self.c.data=copy.deepcopy(original);mutate(self.c.data)
            with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
            self.assert_block_preserved()
    def test_marker_replacement_during_probe_is_not_archived(self):
        self.c.on_observe=lambda:write(self.rt/'UNCERTAIN.json',b'NEW UNKNOWN')
        with self.assertRaises(r.Blocked):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assertEqual((self.rt/'UNCERTAIN.json').read_bytes(),b'NEW UNKNOWN')
    def test_audit_write_fsync_or_rename_failure_preserves_block(self):
        for patcher in [patch.object(r,'write_audit',side_effect=OSError('audit')),patch.object(r,'fsync_dir',side_effect=OSError('fsync'))]:
            with patcher:
                with self.assertRaises(OSError):r.reconcile(self.repo,self.b,self.c,self.d)
            self.assert_block_preserved()
        with self.assertRaises(OSError):r.reconcile(self.repo,self.b,self.c,self.d,rename=lambda *a:(_ for _ in ()).throw(OSError('rename')))
        self.assert_block_preserved()
    def test_no_failure_prone_reads_or_probes_after_archive_commit(self):
        committed=[False];original_read=r.read_bound
        def read(*a,**kw):
            if committed[0]:self.fail('read after archive')
            return original_read(*a,**kw)
        def archive(source,dest):os.rename(source,dest);committed[0]=True
        with patch.object(r,'read_bound',side_effect=read):result=r.reconcile(self.repo,self.b,self.c,self.d,rename=archive)
        self.assertTrue(committed[0]);self.assertEqual(result['generation_requests'],0)
    def test_repeated_reconciliation_does_not_start_any_request_or_modify_summary(self):
        result=r.reconcile(self.repo,self.b,self.c,self.d);calls=len(self.d.calls)
        with self.assertRaises(FileNotFoundError):r.reconcile(self.repo,self.b,self.c,self.d)
        self.assertEqual(len(self.d.calls),calls);self.assertEqual((self.run/'summary.json').read_bytes(),self.summary)
        self.assertEqual(Path(result['archived_marker']).read_bytes(),self.original)
    def test_only_docker_read_queries_are_constructed(self):
        calls=[]
        def query(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0,stdout='')
        reader=r.DockerReadOnly(lambda:None)
        with patch.object(r.subprocess,'run',side_effect=query):reader.absent('a'*64,'fixed-name')
        self.assertEqual(len(calls),2)
        for args in calls:self.assertEqual(args[3:6],['container','ls','-a'])
        self.assertIn('id='+'a'*64,calls[0]);self.assertIn('name=^/fixed-name$',calls[1])
        with patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')):
            with self.assertRaisesRegex(r.Blocked,'NO_PRIVILEGE_RETRY'):reader.absent('a'*64,'fixed-name')
    def test_existing_coordinator_observer_uses_only_fixed_read_operations(self):
        calls=[]
        rt=SimpleNamespace(read=lambda path,end:(calls.append(path) or {}),_threshold=lambda **kw:{})
        observer=r.ExistingReadOnlyCoordinator.__new__(r.ExistingReadOnlyCoordinator)
        observer.c=SimpleNamespace(idle=lambda:(calls.append('existing_idle') or dict(r.STATES)),rt=rt)
        observer.observe()
        self.assertEqual(calls,['existing_idle','/health','/props?model='+r.MODEL+'&autoload=false','/slots?model='+r.MODEL+'&autoload=false'])
    def test_default_cli_is_inert_without_host_helpers_or_marker_read(self):
        with patch.object(r.sys,'argv',['reconcile']),patch.object(r,'load_bindings',side_effect=AssertionError('no reads')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(r.main(),0)
        self.assertIn('PREPARED',output.getvalue())

    def diagnosis_fixture(self):
        profile={'resident_container_id':'b'*64,'router_name':'fixed-router','image':'fixed-image','internal_network_id':'fixed-net-id'}
        self.b['profile_sha256']=write(self.rt/'router-host-profile.json',profile)
        route={'container_id':'c'*64,'image':'fixed-image','network_id':'fixed-net-id','network_name':'fixed-net',
            'ipv4':'172.22.0.2','endpoint_id':'fixed-endpoint','port':8080}
        state={'router_cid':'c'*64,'resident_cid':'b'*64,'route_ipv4':'172.22.0.2',
            'route_endpoint_id':'fixed-endpoint','phase':'DEPLOYED'}
        for attr,name,data in [('DIAG_ROUTE_SHA','router-deployment.json',route),('DIAG_STATE_SHA','router-host-state.json',state)]:
            p=patch.object(r,attr,write(self.rt/name,data));p.start();self.addCleanup(p.stop)
        self.c.daemon_observe=lambda:{'idle':True}
        def inspect(cid,guard):
            guard();return {'id':cid,'name':'/fixed-router','image':'fixed-image','state':False,'status':'exited',
                'networks':{'fixed-net':{'NetworkID':'fixed-net-id','EndpointID':'','IPAddress':''}}}
        return inspect

    def test_diagnosis_is_readonly_and_reports_stopped_stale_router(self):
        inspect=self.diagnosis_fixture()
        with patch.object(r.os,'rename',side_effect=AssertionError('no archive')):
            result=r.diagnose(self.repo,self.b,self.c,inspect)
        self.assert_block_preserved();self.assertFalse((self.rt/'readiness-reconciliation-audits').exists())
        data=result['observations']['router_container']['data']
        self.assertEqual(data['status'],'exited');self.assertFalse(data['receipt_matches']['ipv4'])
        self.assertEqual(result['marker_changes'],0);self.assertEqual(result['generation_requests'],0)

    def test_diagnosis_partial_read_failures_keep_other_evidence(self):
        inspect=self.diagnosis_fixture()
        self.c.observe=lambda:(_ for _ in ()).throw(r.Blocked('READ_STAGE:coordinator_idle:GET:/health:TimeoutError'))
        result=r.diagnose(self.repo,self.b,self.c,inspect)
        self.assertTrue(result['observations']['daemon_status']['ok'])
        failure=result['observations']['router_and_resident_reads']
        self.assertFalse(failure['ok']);self.assertIn('GET:/health',failure['reason']);self.assert_block_preserved()

    def test_diagnosis_changed_fixed_route_blocks_before_reads(self):
        inspect=self.diagnosis_fixture();write(self.rt/'router-deployment.json',{'wrong':'route'})
        with self.assertRaisesRegex(r.Blocked,'HASH_MISMATCH'):r.diagnose(self.repo,self.b,self.c,inspect)
        self.assertEqual(self.c.events,['guard']);self.assert_block_preserved()

    def test_observer_annotates_get_inside_idle_and_restores_method(self):
        observer=r.ExistingReadOnlyCoordinator.__new__(r.ExistingReadOnlyCoordinator)
        def read(path,end):raise TimeoutError('sensitive response must not appear')
        rt=SimpleNamespace(read=read)
        observer.c=SimpleNamespace(rt=rt,idle=lambda:rt.read('/health',123))
        with self.assertRaisesRegex(r.Blocked,'READ_STAGE:coordinator_idle:GET:/health:TimeoutError') as result:observer.observe()
        self.assertNotIn('sensitive',str(result.exception));self.assertIs(rt.read,read)

    def test_observer_distinguishes_idle_before_get_failure(self):
        observer=r.ExistingReadOnlyCoordinator.__new__(r.ExistingReadOnlyCoordinator)
        read=lambda path,end:{}
        observer.c=SimpleNamespace(rt=SimpleNamespace(read=read),idle=lambda:(_ for _ in ()).throw(TimeoutError()))
        with self.assertRaisesRegex(r.Blocked,'coordinator_idle_pre_or_between_GET:TimeoutError'):observer.observe()
        self.assertIs(observer.c.rt.read,read)

    def test_fixed_inspect_projects_metadata_only_and_never_retries(self):
        cid='a'*64;calls=[]
        data={'id':cid,'networks':{'fixed':{'NetworkID':'n','EndpointID':'e','IPAddress':'172.22.0.2',
            'Gateway':'','Aliases':['hidden']}}}
        def command(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0,stdout=json.dumps(data))
        with patch.object(r.subprocess,'run',side_effect=command):out=r.inspect_fixed_container(cid,lambda:None)
        self.assertEqual(calls[0][3:5],['container','inspect']);self.assertEqual(calls[0][-1],cid)
        self.assertNotIn('Aliases',out['networks']['fixed']);self.assertNotIn('.Config.Env',calls[0][-2])
        with patch.object(r.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')) as failed:
            with self.assertRaisesRegex(r.Blocked,'NO_PRIVILEGE_RETRY'):r.inspect_fixed_container(cid,lambda:None)
        self.assertEqual(failed.call_count,1)


if __name__=='__main__':unittest.main()
