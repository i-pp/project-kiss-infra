"""Synthetic fixed evidence, fake read-only host and clock. No model/container."""
import copy
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import reconcile_restored_swap as s
import stable_swap_policy as policy

HERE=Path(__file__).resolve().parent
PREP=HERE if (HERE/'test_readiness_reconcile.py').exists() else HERE.parent/'readiness-timeout-diagnosis'
sys.path.insert(0,str(PREP))
import reconcile_vllm_readiness as r
spec=importlib.util.spec_from_file_location('original_fixture',PREP/'test_readiness_reconcile.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
BOOT='5b850071-086f-43a5-8796-b00537607d8b'


class Clock:
    def __init__(self):self.value=0
    def __call__(self):self.value+=.001;return self.value
    def sleep(self,n):self.value+=n


class ContinuedReconcileTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReconcileTests('test_default_cli_is_inert_without_host_helpers_or_marker_read')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.clock=Clock();self.c=self.f.c;self.c.data['resources']['swap_used_bytes']=577536
        self.resource=copy.deepcopy(self.c.data['resources'])
        self.c.c=SimpleNamespace(rt=SimpleNamespace(probe=lambda:copy.deepcopy(self.resource)))
        self.c.daemon_observe=lambda:{'idle':True}
        self.case={'boot_id':BOOT,'swap_baseline_bytes':577536,'approval_request':'fixed-approval','router_cid':'c'*64}
        self.vm={'pswpin':0,'pswpout':141};self.live_calls=[]
        self.h=SimpleNamespace();self.m=SimpleNamespace()
        self.loader=patch.object(s,'load_case',return_value=self.case);self.loader.start();self.addCleanup(self.loader.stop)
        self.live=patch.object(s,'verify_live',side_effect=lambda *a:self.live_calls.append(a));self.live.start();self.addCleanup(self.live.stop)
    def run_case(self,**kw):
        args={'clock':self.clock,'sleep':self.clock.sleep,'read_boot':lambda:BOOT,'read_vmstat':lambda:dict(self.vm)};args.update(kw)
        return s.reconcile_case(self.f.repo,r,self.h,self.f.b,self.case,self.c,self.f.d,self.m,policy,**args)
    def test_full_fixed_reconciliation_archives_original_bytes_only(self):
        result=self.run_case()
        self.assertEqual(result['status'],'RECONCILED_FIXED_RESTORED_SWAP_NO_GENERATION')
        self.assertFalse((self.f.rt/'UNCERTAIN.json').exists())
        self.assertEqual(Path(result['archived_marker']).read_bytes(),self.f.original)
        self.assertEqual((self.f.run/'summary.json').read_bytes(),self.f.summary);self.assertTrue(self.f.attempt.exists())
        audit=json.loads((Path(result['audit_directory'])/'audit.json').read_text())
        proof=audit['swap_stability'];self.assertGreaterEqual(proof['samples'][-1]['elapsed']-proof['samples'][0]['elapsed'],10)
        self.assertTrue((Path(result['audit_directory'])/'precommit.json').exists())
        self.assertEqual(len(self.live_calls),2);self.assertEqual(len(self.f.d.calls),2)
        self.assertEqual(result['container_mutations'],0);self.assertEqual(result['generation_requests'],0)
    def test_boot_change_preserves_marker(self):
        with self.assertRaisesRegex(s.Blocked,'BOOT_CHANGED'):self.run_case(read_boot=lambda:'other')
        self.f.assert_block_preserved()
    def test_swap_growth_or_io_change_or_ram_pressure_preserves_marker(self):
        for field,value in [('swap_used_bytes',581632),('available_bytes',16*(1<<30))]:
            with self.subTest(field=field):
                self.resource[field]=value
                with self.assertRaises(policy.PolicyBlocked):self.run_case()
                self.resource=copy.deepcopy(self.c.data['resources']);self.f.assert_block_preserved()
        calls=[]
        def io_change():
            calls.append(1);return {'pswpin':0,'pswpout':141+int(len(calls)>2)}
        with self.assertRaisesRegex(policy.PolicyBlocked,'SWAP_IO_CHANGED'):self.run_case(read_vmstat=io_change)
        self.f.assert_block_preserved()
    def test_final_health_or_new_trial_container_prevents_archive(self):
        count=[]
        def changed():
            count.append(1)
            if len(count)>1:self.c.data['health']={'status':'bad'}
        self.c.on_observe=changed
        with self.assertRaises(s.Blocked):self.run_case()
        self.f.assert_block_preserved()
        self.c.on_observe=None;self.c.data['health']={'status':'ok'};self.f.d.present=True
        with self.assertRaises(r.Blocked):self.run_case()
        self.f.assert_block_preserved()
    def test_renamed_marker_or_changed_fixed_receipt_blocks_commit(self):
        original=s.load_case;calls=[]
        def changed(*args):
            calls.append(1)
            if len(calls)>1:raise s.Blocked('FIXED_CASE_FILES_CHANGED')
            return self.case
        with patch.object(s,'load_case',side_effect=changed),self.assertRaises(s.Blocked):self.run_case()
        self.f.assert_block_preserved()
    def test_audit_failure_or_rename_failure_never_deletes_marker(self):
        actual=r.write_audit
        def fail(path,value):
            if path.name=='precommit.json':raise OSError('fixture precommit write')
            return actual(path,value)
        with patch.object(r,'write_audit',side_effect=fail),self.assertRaises(OSError):self.run_case()
        self.f.assert_block_preserved()
        def no_rename(*args):raise OSError('fixture rename')
        with self.assertRaises(OSError):self.run_case(rename=no_rename)
        self.f.assert_block_preserved()
    def test_late_final_resource_change_preserves_marker(self):
        actual=r.write_audit
        def change(path,value):
            result=actual(path,value)
            if path.name=='audit.json':self.resource['swap_used_bytes']+=4096
            return result
        with patch.object(r,'write_audit',side_effect=change),self.assertRaises(policy.PolicyBlocked):self.run_case()
        self.f.assert_block_preserved()
    def test_original_default_zero_swap_policy_unchanged(self):
        with self.assertRaisesRegex(r.Blocked,'CURRENT_RESOURCES_NOT_RECONCILABLE'):r.validate_current(self.c.data)
        self.f.assert_block_preserved()
    def test_current_exact_model_and_slot_resource_guards(self):
        for change in [lambda d:d['slots'][0].update(is_processing=True),lambda d:d['resources'].update(gpu_used_bytes=59*(1<<30)),
                lambda d:d['properties'].update(total_slots=True),lambda d:d['resources'].update(swap_used_bytes=0)]:
            value=copy.deepcopy(self.c.data);change(value)
            with self.assertRaises(s.Blocked):s.validate_ready(value,r,577536)
    def test_default_cli_inert(self):
        with patch.object(sys,'argv',['reconcile']),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(s.main(),0)
        self.assertIn('PREPARED_ONLY_NO_ACTION',out.getvalue())

    def test_live_identity_verify_path_has_no_mutation_calls(self):
        calls=[]
        state={'Running':True,'Status':'running','Pid':42,'Paused':False,'Restarting':False,'Dead':False,'OOMKilled':False}
        value={'Id':'c'*64,'State':state,'HostConfig':{'RestartPolicy':{'Name':'no'}}}
        def event(name):return lambda:calls.append(name)
        def route(**kw):
            self.assertEqual(kw,{'verify_only':True});calls.append('verify_only')
        m=SimpleNamespace(human_guard=event('host'),verify_preset=event('preset'),route_precheck=event('route'),
            original=lambda:({'State':{'Running':False}},'fingerprint'),owned_router=lambda:value,
            capture_internal_route=route)
        self.live.stop();s.verify_live(m,self.case)
        self.assertEqual(calls,['host','preset','route','verify_only'])
        for key in ('Running','OOMKilled','Paused'):
            before=state[key];state[key]=not before
            with self.assertRaises(s.Blocked):s.verify_live(m,self.case)
            state[key]=before

    def test_failed_probe_value_retained_in_private_failure_audit(self):
        self.resource['swap_used_bytes']+=4096
        with self.assertRaises(policy.PolicyBlocked) as failed:self.run_case()
        report=json.loads((Path(failed.exception.reconciliation_audit)/'failure.json').read_text())
        self.assertEqual(report['last_attempted_sample']['resources']['swap_used_bytes'],581632)
        self.f.assert_block_preserved()


if __name__=='__main__':unittest.main()
