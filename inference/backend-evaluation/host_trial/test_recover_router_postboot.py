"""CPU temporary fixtures only; no host guard/import, real Docker or API."""
import copy
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import recover_router_postboot as recovery

PREP=Path(__file__).resolve().parent
if not (PREP/'test_readiness_reconcile.py').exists():
    PREP=PREP.parent/'readiness-timeout-diagnosis'
sys.path.insert(0,str(PREP))
import reconcile_vllm_readiness as r
spec=importlib.util.spec_from_file_location('fixture_module',PREP/'test_readiness_reconcile.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)


class Maintenance:
    def __init__(self,fixture):
        self.f=fixture;self.profile=json.loads((fixture.rt/'router-host-profile.json').read_text())
        self.repo=fixture.repo;self.llm=fixture.repo/'agents/local_llm'
        self.state=json.loads((fixture.rt/'router-host-state.json').read_text());self.events=[]
        self.original_running=False;self.running=False;self.missing=False;self.changed=False;self.policy='no'
        self.start_error=None;self.gate_error=None;self.inspect_count=0
    def original(self):return {'State':{'Running':self.original_running}},'fixture-fingerprint'
    def owned_router(self):
        self.inspect_count+=1
        if self.missing:return None
        return {'Id':self.state['router_cid'] if not self.changed else 'd'*64,
            'State':{'Running':self.running,'Paused':False,'Restarting':False,'Dead':False,
                'Status':'running' if self.running else 'exited','Pid':42 if self.running else 0},
            'HostConfig':{'RestartPolicy':{'Name':self.policy}}}
    def human_guard(self):self.events.append('host_guard')
    def device_check(self):self.events.append('device_check')
    def verify_preset(self):self.events.append('verify_preset')
    def network(self,strict):
        if strict is not True:raise AssertionError('strict required')
        self.events.append('strict_network')
    def route_precheck(self):self.events.append('route_precheck')
    def enter(self,step):self.events.append(step);self.step=step
    def save(self,phase):self.state['phase']=phase;self.events.append('save:'+phase)
    def docker(self,*args,**kwargs):
        self.events.append(tuple(args))
        if args!=('start','c'*64):raise AssertionError('fixed start only')
        if self.start_error:raise self.start_error
        self.running=True
    def retire_routes(self):self.events.append('retire_routes')
    def router_gate(self):
        self.events.append('router_gate')
        if self.gate_error:raise self.gate_error


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ReconcileTests('test_default_cli_is_inert_without_host_helpers_or_marker_read')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.diagnosis_fixture();self.c=self.fixture.c
        self.c.c=SimpleNamespace(rt=SimpleNamespace(_threshold=lambda **kwargs:fixtures.current()['resources']))
        self.m=Maintenance(self.fixture);self.d=fixtures.Docker()
    def run_recovery(self):return recovery.recover(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d)
    def assert_preserved(self):
        self.fixture.assert_block_preserved()
        self.assertFalse((self.fixture.rt/'readiness-reconciliation-audits').exists())
    def test_fixed_existing_start_once_ready_no_archive_or_stop(self):
        result=self.run_recovery();self.assert_preserved()
        self.assertEqual(result['status'],'OWNED_ROUTER_30B_READY_UNKNOWN_PRESERVED')
        self.assertEqual(result['start_requests'],1)
        self.assertEqual([e for e in self.m.events if isinstance(e,tuple)],[('start','c'*64)])
        self.assertLess(self.m.events.index('retire_routes'),self.m.events.index('router_gate'))
        self.assertTrue((self.fixture.rt/recovery.INTENT).exists())
        before=json.loads((Path(result['audit_directory'])/'before.json').read_text())
        self.assertEqual(before['marker_sha256'],self.fixture.b['marker_sha256'])
        with self.assertRaisesRegex(recovery.RecoveryBlocked,'INTENT_EXISTS'):self.run_recovery()
    def test_original_running_blocks_without_stop_or_intent(self):
        self.m.original_running=True
        with self.assertRaisesRegex(recovery.RecoveryBlocked,'ORIGINAL30B_RUNNING'):self.run_recovery()
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()
    def test_missing_wrong_router_or_restart_policy_blocks(self):
        for field,value in [('missing',True),('changed',True),('policy','always')]:
            with self.subTest(field=field):
                setattr(self.m,field,value)
                with self.assertRaises(recovery.RecoveryBlocked):self.run_recovery()
                setattr(self.m,field,False if field!='policy' else 'no')
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()
    def test_already_running_router_refresh_has_zero_start(self):
        self.m.running=True;result=self.run_recovery()
        self.assertEqual(result['start_requests'],0);self.assert_preserved()
    def test_start_timeout_never_repeats_retires_or_rolls_back(self):
        self.m.start_error=TimeoutError()
        with self.assertRaises(TimeoutError):self.run_recovery()
        self.assertNotIn('retire_routes',self.m.events)
        intent=json.loads((self.fixture.rt/recovery.INTENT).read_text())
        terminal=json.loads((Path(intent['audit_directory'])/'terminal.json').read_text())
        self.assertEqual(terminal['start_requests'],1)
        with self.assertRaisesRegex(recovery.RecoveryBlocked,'INTENT_EXISTS'):self.run_recovery()
        self.assertEqual([e for e in self.m.events if isinstance(e,tuple)],[('start','c'*64)])
        self.assert_preserved()
    def test_gate_failure_no_automatic_original_start_or_router_stop(self):
        self.m.gate_error=RuntimeError()
        with self.assertRaises(RuntimeError):self.run_recovery()
        self.assertEqual([e for e in self.m.events if isinstance(e,tuple)],[('start','c'*64)])
        self.assert_preserved()
    def test_audit_failure_prevents_start(self):
        with patch.object(r,'write_audit',side_effect=OSError()):
            with self.assertRaises(OSError):self.run_recovery()
        self.assertEqual([e for e in self.m.events if isinstance(e,tuple)],[]);self.assert_preserved()
    def test_fixed_state_changed_and_swap_nonzero_block(self):
        self.m.state['phase']='FAILED'
        with self.assertRaisesRegex(recovery.RecoveryBlocked,'SCOPE_CHANGED'):self.run_recovery()
        self.m.state['phase']='DEPLOYED'
        self.c.c.rt._threshold=lambda **kwargs:{'swap_used_bytes':1}
        with self.assertRaisesRegex(recovery.RecoveryBlocked,'SWAP'):self.run_recovery()
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()
    def test_default_is_inert(self):
        with patch.object(sys,'argv',['recover']),patch.object(recovery,'pinned_import',side_effect=AssertionError('no import')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(recovery.main(),0)
        self.assertIn('PREPARED_ONLY',out.getvalue())

    def test_one_command_recovers_then_archives_with_original_summary_preserved(self):
        marker=self.fixture.original;summary=self.fixture.summary
        with redirect_stdout(io.StringIO()):
            result=recovery.recover_and_reconcile(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d)
        self.assertEqual(result['status'],'EXISTING_ROUTER_RESTORED_AND_READINESS_RECONCILED')
        self.assertFalse((self.fixture.rt/'UNCERTAIN.json').exists())
        archive=Path(result['reconciliation']['archived_marker'])
        self.assertEqual(archive.read_bytes(),marker)
        self.assertEqual((self.fixture.run/'summary.json').read_bytes(),summary)
        self.assertTrue(self.fixture.attempt.exists())
        self.assertEqual(len(self.d.calls),3)  # before start, before and after final reads

    def test_old_trial_container_present_prevents_start(self):
        self.d.present=True
        with self.assertRaises(r.Blocked):self.run_recovery()
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists())
        self.assertFalse(any(isinstance(e,tuple) for e in self.m.events));self.assert_preserved()

    def test_archive_probe_failure_after_ready_preserves_marker_and_start_intent(self):
        calls=[]
        def observe():
            calls.append(1)
            if len(calls)==2:raise TimeoutError('fixed fixture')
            return fixtures.current()
        self.c.observe=observe
        with self.assertRaises(TimeoutError):
            recovery.recover_and_reconcile(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d)
        self.assertTrue((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()
        self.assertEqual([e for e in self.m.events if isinstance(e,tuple)],[('start','c'*64)])

    def test_readonly_preflight_never_mutates_or_consumes_start(self):
        before={n:(self.fixture.rt/n).read_bytes() for n in ['UNCERTAIN.json','router-host-state.json','router-deployment.json']}
        with patch.object(self.m,'save',side_effect=AssertionError('no state save')),patch.object(r,'reconcile',side_effect=AssertionError('no reconcile')):
            result=recovery.run_audited(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d,True)
        self.assertEqual(result['status'],'READONLY_RECOVERY_PREFLIGHT_PASS')
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists())
        for n,raw in before.items():self.assertEqual((self.fixture.rt/n).read_bytes(),raw)
        self.assertFalse(any(isinstance(e,tuple) for e in self.m.events))

    def router_object(self):
        return {'Id':self.m.state['router_cid'],'Name':'/'+self.m.profile['router_name'],
            'Image':self.m.profile['image'],'Path':'/app/llama-server',
            'Args':['--models-preset','/config/models.ini','--models-max','1','--no-models-autoload','--host','0.0.0.0','--port','8080','--offline','--no-ui'],
            'Config':{'User':str(os.getuid())+':'+str(os.getgid()),'Labels':{'com.docker.compose.project':'project-kiss-aceis-router','io.aceis.deployment':self.m.state.get('token')},'Env':['SECRET_MUST_NOT_BE_SAVED']},
            'HostConfig':{'Memory':34359738368,'MemorySwap':34359738368,'NanoCpus':8000000000,'PidsLimit':512,
                'ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':None,'SecurityOpt':['no-new-privileges:true'],
                'PortBindings':{'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]}},
            'NetworkSettings':{'Networks':{'project-kiss-large-coder-b3_local':{}}},
            'Mounts':[{'Type':'bind','Destination':k,'Source':str(v),'RW':rw} for k,v,rw in [
                ('/models',self.m.repo/'models',False),('/cache',self.m.repo/'.cache/large-coder-b3/runtime',True),
                ('/config/models.ini',self.m.llm/'integration/router-presets.PROPOSAL.ini',False)]]}

    def test_numeric_gid_difference_is_diagnosed_without_acceptance(self):
        value=self.router_object();value['Config']['User']='1000:973'
        with patch.object(recovery.os,'getuid',return_value=1000),patch.object(recovery.os,'getgid',return_value=1000):
            info=recovery.contract_observation(self.m,value)
        self.assertEqual(info['mismatches'],['user'])
        self.assertEqual(info['container_user'],'1000:973');self.assertEqual(info['current_user'],'1000:1000')

    def test_failure_code_stage_and_safe_inspect_saved_before_start(self):
        class Failure(RuntimeError):code='ROUTER_CONTRACT_MISMATCH'
        value=self.router_object();value['Config']['User']='1000:973'
        self.m.inspect=lambda identity:value
        def fail():
            self.m.inspect(self.m.profile['router_name'])
            raise Failure('Fixed contract differs')
        self.m.owned_router=fail
        with self.assertRaises(Failure) as raised:
            recovery.run_audited(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d,True)
        report=json.loads((Path(raised.exception.recovery_audit)/'failure.json').read_text())
        self.assertEqual(report['error_code'],'ROUTER_CONTRACT_MISMATCH')
        self.assertEqual(report['stage'],'verify_fixed_owned_router_contract')
        self.assertIn('user',report['observations']['router_contract']['mismatches'])
        self.assertFalse(report['start_intent_exists']);self.assertFalse((self.fixture.rt/recovery.INTENT).exists())
        self.assertNotIn('SECRET_MUST_NOT_BE_SAVED',json.dumps(report))
        self.assert_preserved()

    def test_label_secret_and_arbitrary_user_never_in_diagnostic(self):
        value=self.router_object();value['Config']['Labels']['io.aceis.deployment']='DEPLOYMENT_TOKEN_MUST_NOT_BE_SAVED'
        value['Config']['User']='USER_SECRET_MUST_NOT_BE_SAVED'
        info=recovery.contract_observation(self.m,value)
        self.assertIn('deployment_label',info['mismatches']);self.assertIn('user',info['mismatches'])
        self.assertNotIn('MUST_NOT_BE_SAVED',json.dumps(info))

    def test_docker_read_denial_does_not_start_or_retry(self):
        class Failure(RuntimeError):code='DOCKER_PERMISSION_DENIED'
        calls=[]
        def absent(*args):calls.append(args);raise Failure('Denied')
        self.d.absent=absent
        with self.assertRaises(Failure) as raised:
            recovery.run_audited(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d,True)
        report=json.loads((Path(raised.exception.recovery_audit)/'failure.json').read_text())
        self.assertEqual(report['error_code'],'DOCKER_PERMISSION_DENIED');self.assertEqual(len(calls),1)
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()

    def test_malformed_inspect_diagnostics_do_not_mask_guard_failure(self):
        class Failure(RuntimeError):code='ROUTER_CONTRACT_MISMATCH'
        value=self.router_object();value['Config']=None
        self.m.inspect=lambda identity:value
        def guard():
            self.assertIs(self.m.inspect(self.m.profile['router_name']),value)
            raise Failure('Original guard exception')
        self.m.owned_router=guard
        with self.assertRaises(Failure) as raised:
            recovery.run_audited(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d,True)
        report=json.loads((Path(raised.exception.recovery_audit)/'failure.json').read_text())
        self.assertEqual(report['error_code'],'ROUTER_CONTRACT_MISMATCH')
        self.assertEqual(report['observations']['router_contract']['observation_error_class'],'AttributeError')
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()

    def test_failed_failure_audit_write_retains_original_error_code(self):
        class Failure(RuntimeError):code='ROUTER_CONTRACT_MISMATCH'
        self.m.owned_router=lambda:(_ for _ in ()).throw(Failure('Fixed failure'))
        actual=r.write_audit
        def write(path,value):
            if path.name=='failure.json':raise OSError('fixture audit failure')
            return actual(path,value)
        with patch.object(r,'write_audit',side_effect=write),self.assertRaises(Failure) as raised:
            recovery.run_audited(self.fixture.repo,r,self.fixture.b,self.m,self.c,self.d,True)
        self.assertEqual(recovery.exception_code(raised.exception),'ROUTER_CONTRACT_MISMATCH')
        self.assertEqual(raised.exception.audit_write_error,'OSError')
        self.assertFalse((self.fixture.rt/recovery.INTENT).exists());self.assert_preserved()

    def user_fixture(self,mutate=None):
        user=str(os.getuid())+':973';directory='router-postboot-diagnostics-'+'d'*32
        source='router-user-evidence-vllm-8949115c'
        report={'error_code':'ROUTER_CONTRACT_MISMATCH','stage':'verify_fixed_owned_router_contract',
            'diagnose_only':True,'start_intent_exists':False,'generation_requests':0,'observations':{
                'original30b':{'present':True,'running':False},'router_contract':{
                    'matches':{k:k!='user' for k in recovery.CONTRACT_FIELDS},'mismatches':['user'],
                    'container_user':user,'state':{'Status':'exited','Running':False,'Pid':0,'ExitCode':0,'OOMKilled':False}}}}
        if mutate:mutate(report)
        started={'mode':'readonly','run':self.fixture.b['run_name'],'marker_sha256':self.fixture.b['marker_sha256'],'automatic_retry':False}
        d={'schema':1,'purpose':'fixed_existing_router_user_comparison_only','expected_user':user,
            'router_cid':self.m.state['router_cid'],'run_name':self.fixture.b['run_name'],
            'profile_sha256':self.fixture.b['profile_sha256'],'marker_sha256':self.fixture.b['marker_sha256'],
            'route_sha256':r.DIAG_ROUTE_SHA,'state_sha256':r.DIAG_STATE_SHA,
            'diagnostic_directory':directory,'source_evidence_directory':source,
            'source_sha256':{n:fixtures.write(self.fixture.rt/source/n,b'CPU ONLY SOURCE EVIDENCE')
                for n in ['host_router_maintenance.before.py','recover_router_postboot.before.py']},
            'diagnostic_sha256':{n:fixtures.write(self.fixture.rt/directory/n,v) for n,v in [('failure.json',report),('started.json',started)]}}
        digest=fixtures.write(self.fixture.rt/recovery.USER_BINDINGS,d)
        scoped=patch.object(recovery,'USER_BINDINGS_SHA',digest);scoped.start();self.addCleanup(scoped.stop)
        return d

    def test_only_fixed_diagnostic_binds_existing_user(self):
        self.user_fixture()
        self.assertEqual(recovery.load_existing_user(self.fixture.repo,r,self.fixture.b),str(os.getuid())+':973')
        self.assert_preserved()

    def test_another_mismatch_or_missing_field_or_nonbool_refuses_user_binding(self):
        for mutate in [lambda p:p['observations']['router_contract']['matches'].__setitem__('memory',False),
                lambda p:p['observations']['router_contract']['matches'].pop('readonly'),
                lambda p:p['observations']['router_contract']['matches'].__setitem__('image',1),
                lambda p:p.__setitem__('start_intent_exists',0)]:
            with self.subTest(mutate=mutate):
                self.user_fixture(mutate)
                with self.assertRaisesRegex(recovery.RecoveryBlocked,'DIAGNOSTIC_NOT_PROVEN'):
                    recovery.load_existing_user(self.fixture.repo,r,self.fixture.b)
                self.assert_preserved()

    def test_changed_diagnostic_bytes_or_missing_source_refuses_user_binding(self):
        d=self.user_fixture()
        (self.fixture.rt/d['diagnostic_directory']/'failure.json').write_text('{}')
        with self.assertRaises(r.Blocked):recovery.load_existing_user(self.fixture.repo,r,self.fixture.b)
        d=self.user_fixture();(self.fixture.rt/d['source_evidence_directory']/'host_router_maintenance.before.py').unlink()
        with self.assertRaises(FileNotFoundError):recovery.load_existing_user(self.fixture.repo,r,self.fixture.b)
        self.assert_preserved()


if __name__=='__main__':unittest.main()
