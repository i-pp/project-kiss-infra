"""Temporary-fixture terminal bookkeeping; no real host or model operation."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
MODULE=HERE/'resolve_terminal_record.py'
if not MODULE.exists():MODULE=HERE/'resolve_terminal_record.PROPOSAL.py'
spec=importlib.util.spec_from_file_location('terminal_proposal',MODULE)
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
PREP=HERE if (HERE/'test_readiness_reconcile.py').exists() else HERE.parent/'readiness-timeout-diagnosis'
sys.path.insert(0,str(PREP))
import reconcile_vllm_readiness as r
spec=importlib.util.spec_from_file_location('terminal_fixtures',PREP/'test_readiness_reconcile.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)


class TerminalResolutionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReconcileTests('test_default_cli_is_inert_without_host_helpers_or_marker_read')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.c=self.f.c
        self.c.daemon_observe=lambda:{'idle':True}
        self.case={'boot_id':'fixed-boot'};self.live=[]
        self.s=SimpleNamespace(load_case=lambda *a:copy.deepcopy(self.case),verify_live=lambda *a:self.live.append(a),boot=lambda:'fixed-boot')
        self.h=SimpleNamespace();self.m=SimpleNamespace()
        self.c.data['resources']={'status':'OBSERVED_NOT_ADMISSION_GATE','values':{'available_bytes':50*(1<<30),'gpu_used_bytes':21*(1<<30),'swap_used_bytes':581632}}
        p=patch.object(t,'APPROVAL_REQUEST','TEST_FIXTURE_ONLY');p.start();self.addCleanup(p.stop)
    def resolve(self,**kw):
        return t.resolve(self.f.repo,r,self.s,self.h,self.f.b,self.case,self.c,self.f.d,self.m,
            observe=lambda c,r:c.observe(),**kw)
    def test_known_terminal_failure_archives_original_without_rewriting_history(self):
        result=self.resolve();record=json.loads(Path(result['resolution']).read_text())
        self.assertEqual(Path(result['archived_marker']).read_bytes(),self.f.original)
        self.assertEqual((self.f.run/'summary.json').read_bytes(),self.f.summary);self.assertTrue(self.f.attempt.exists())
        self.assertEqual(record['environment'],'FAIL');self.assertEqual(record['quality'],'UNASSESSED')
        self.assertFalse(record['new_inference_authorized']);self.assertEqual(record['generation_requests'],0)
        self.assertEqual(record['historical_original_status'],'UNKNOWN');self.assertEqual(len(self.f.d.calls),2)
        self.assertEqual(len(self.live),2);self.assertFalse((self.f.rt/'UNCERTAIN.json').exists())
    def test_resource_variation_or_missing_telemetry_is_recorded_not_admission_gate(self):
        self.c.data['resources']={'status':'UNAVAILABLE_NOT_ADMISSION_GATE','error_class':'OSError'}
        result=self.resolve();record=json.loads(Path(result['resolution']).read_text())
        self.assertEqual(record['current_restoration']['resources']['error_class'],'OSError')
        self.assertFalse(record['new_inference_authorized'])
    def test_actual_generation_or_intent_evidence_refuses_resolution(self):
        self.f.changed_run('summary.json',lambda d:d.update(generation_requests=1))
        with self.assertRaises(r.Blocked):self.resolve()
        self.assertEqual((self.f.rt/'UNCERTAIN.json').read_bytes(),self.f.original)
    def test_request_file_refuses_resolution(self):
        fixtures.write(self.f.run/'post-intent.json',{'generation_request':True})
        with self.assertRaises(r.Blocked):self.resolve()
        self.f.assert_block_preserved()
    def test_container_presence_or_busy_slot_refuses_resolution(self):
        self.f.d.present=True
        with self.assertRaises(r.Blocked):self.resolve()
        self.f.d.present=False;self.c.data['slots'][0]['is_processing']=True
        with self.assertRaises(t.Blocked) as fail:self.resolve()
        self.f.assert_block_preserved()
        audit=json.loads((Path(fail.exception.reconciliation_audit)/'failure.json').read_text())
        self.assertTrue(audit['current_observation']['slots'][0]['is_processing'])
    def test_wrong_boot_or_case_or_marker_refuses_resolution(self):
        with self.assertRaises(t.Blocked):self.resolve(read_boot=lambda:'other')
        self.s.load_case=lambda *a:{'other':'case'}
        with self.assertRaises(t.Blocked):self.resolve()
        self.f.assert_block_preserved()
    def test_changed_fixed_source_refuses_resolution(self):
        (self.f.repo/'fixed_source.py').write_text('changed source')
        with self.assertRaises(r.Blocked):self.resolve()
        self.assertEqual((self.f.rt/'UNCERTAIN.json').read_bytes(),self.f.original)
    def test_resolution_write_or_atomic_rename_failure_preserves_original(self):
        actual=r.write_audit
        def fail(path,value):
            if path.name=='resolution.json':raise OSError('fixture write')
            return actual(path,value)
        with patch.object(r,'write_audit',side_effect=fail),self.assertRaises(OSError):self.resolve()
        self.f.assert_block_preserved()
        def rename(*a):raise OSError('fixture rename')
        with self.assertRaises(OSError):self.resolve(rename=rename)
        self.f.assert_block_preserved()
    def test_owner_approval_pending_has_no_observation_or_audit(self):
        with patch.object(t,'APPROVAL_REQUEST','PENDING_NOT_AUTHORIZED'),self.assertRaises(t.Blocked):self.resolve()
        self.assertEqual(self.c.events,[]);self.assertFalse((self.f.rt/'readiness-reconciliation-audits').exists())
    def test_original_resource_guard_and_future_admission_unchanged(self):
        original=fixtures.current();original['resources']['swap_used_bytes']=581632
        with self.assertRaises(r.Blocked):r.validate_current(original)
        self.f.assert_block_preserved()
    def test_raw_get_observer_never_calls_allocation_preflight(self):
        expected=fixtures.current();calls=[]
        def fail(*a,**k):raise AssertionError('allocation/lifecycle must not run')
        rt=SimpleNamespace(require_deployment=lambda:calls.append('deployment'),snapshot=lambda deadline:expected['models'],
            read=lambda path,end:expected['health'] if path=='/health' else expected['properties'] if path.startswith('/props') else expected['slots'],
            probe=lambda:{'swap_used_bytes':999999},_threshold=fail,_post=fail)
        c=SimpleNamespace(guard=lambda:calls.append('guard'),daemon_observe=lambda:calls.append('idle'),c=SimpleNamespace(rt=rt),idle=fail)
        value=t.observe_restoration(c,r);t.validate_restoration(value,r)
        self.assertEqual(value['resources']['values']['swap_used_bytes'],999999)
        rt.probe=lambda:(_ for _ in ()).throw(OSError('fixture unavailable'))
        value=t.observe_restoration(c,r);t.validate_restoration(value,r)
        self.assertEqual(value['resources']['status'],'UNAVAILABLE_NOT_ADMISSION_GATE')


if __name__=='__main__':unittest.main()
