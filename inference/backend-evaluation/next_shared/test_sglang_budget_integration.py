"""CPU fake backend/operator/probes only. No host model, Docker or HTTP."""
import copy
import json
import unittest
from unittest.mock import patch
import host_api_trial as h
import test_host_api_trial as base_tests
from paging_telemetry import PagingTelemetry


class TelemetryFake:
    def sample(self,*a):pass
    def snapshot(self):return {'status':'FAKE_CPU_ONLY'}


class ScopedBudgetTests(unittest.TestCase):
    def fixture(self):
        base=base_tests.TrialTests();base.setUp();self.addCleanup(base.tearDown);return base
    def execute(self,base,backend='sglang',digest=None,**kwargs):
        real=h.Trial
        def factory(*args,**kw):kw['operator_sha256']=digest or h.SG_SWAP_OPERATOR_SHA;return real(*args,**kw)
        with patch.object(h,'Trial',side_effect=factory),patch.object(h,'PagingTelemetry',TelemetryFake):return base.execute(backend,**kwargs)
    def test_measured_small_asset_hash_drift_passes_same_one_generation(self):
        base=self.fixture();value={'swap':581632}
        def verify(path,**kw):value['swap']=2777088;kw['check']();return []
        t,result=self.execute(base,probe=lambda:{**base_tests.healthy(),'swap_used':value['swap']},verify=verify)
        self.assertEqual(result['status'],'COMPLETED');self.assertEqual(base.http.posts,1)
        self.assertEqual(result['swap_growth_policy']['baseline']['swap_used'],581632)
        self.assertEqual(result['swap_growth_policy']['max_growth_bytes'],128<<20)
        self.assertEqual(result['startup_budget_seconds'],300)
        policy=json.loads((t.run/'resource-policy.json').read_text());self.assertFalse(policy['baseline_reset_after_assets'])
    def test_excess_hash_growth_stops_before_attempt_or_unload_and_latches_first_value(self):
        base=self.fixture();value={'swap':581632};reserved=[]
        def verify(path,**kw):value['swap']+=129<<20;kw['check']();return []
        t,result=self.execute(base,probe=lambda:{**base_tests.healthy(),'swap_used':value['swap']},verify=verify,reserve=lambda:reserved.append(1))
        self.assertEqual(result['status'],'FAILED');self.assertEqual(result['environment'],'NOT_RUN')
        self.assertNotIn('unload',base.c.events);self.assertEqual(base.http.posts,0);self.assertEqual(reserved,[])
        first=copy.deepcopy(t.resource_failure);value['swap']=581632
        with self.assertRaises(h.Blocked):t.safety()
        self.assertEqual(t.resource_failure,first)
        events=[json.loads(p.read_text()) for p in t.run.glob('event-*.json')]
        self.assertEqual(sum(e['event']=='resource_threshold_exceeded' for e in events),1)
        self.assertEqual(first['observed']['swap_used'],581632+(129<<20))
    def test_vllm_and_unreviewed_sg_operator_keep_original_zero_growth(self):
        for backend,digest in [('vllm',h.SG_SWAP_OPERATOR_SHA),('sglang','a'*64)]:
            base=self.fixture();value={'swap':581632}
            def verify(path,**kw):value['swap']+=4096;kw['check']();return []
            _,result=self.execute(base,backend,digest,probe=lambda:{**base_tests.healthy(),'swap_used':value['swap']},verify=verify)
            self.assertEqual(result['status'],'FAILED');self.assertEqual(base.http.posts,0)
            self.assertEqual(result['swap_growth_policy']['max_growth_bytes'],0)
    def test_approved_scope_still_rejects_old_ram_and_gpu_limits(self):
        for key,value in [('mem_available',23*h.GIB),('gpu_used',59*h.GIB),('gpu_used',None)]:
            base=self.fixture()
            t,result=self.execute(base,probe=lambda:{**base_tests.healthy(),key:value})
            self.assertEqual(result['status'],'FAILED');self.assertNotIn('unload',base.c.events)
            self.assertEqual(base.http.posts,0);self.assertIsNotNone(t.resource_failure)
    def test_scoped_growth_after_start_owns_cleanup_and_restores(self):
        base=self.fixture()
        def probe():return {**base_tests.healthy(),'swap_used':581632+((129<<20) if 'start' in base.d.events else 0)}
        _,result=self.execute(base,probe=probe)
        self.assertEqual(result['status'],'FAILED');self.assertEqual(base.http.posts,0)
        self.assertTrue(result['cleanup_confirmed']);self.assertIn('restore',base.c.events)
    def test_active_post_pressure_is_unknown_and_never_resent(self):
        base=self.fixture();base.http.mode='wait_for_resource_abort'
        def probe():return {**base_tests.healthy(),'swap_used':581632+((129<<20) if base.http.posts else 0)}
        _,result=self.execute(base,probe=probe)
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(base.http.posts,1)
        self.assertTrue(any(e.startswith('uncertain:') for e in base.c.events));self.assertIn('restore',base.c.events)

    def test_probe_exception_after_baseline_is_sticky_and_not_fabricated(self):
        base=self.fixture()
        def probe():
            if 'start' in base.d.events:raise OSError('fixture probe unavailable')
            return {**base_tests.healthy(),'swap_used':581632}
        t,result=self.execute(base,probe=probe)
        self.assertEqual(result['generation_requests'],0);self.assertIsNone(t.resource_failure['observed'])
        self.assertEqual(t.resource_failure['probe_error_class'],'OSError')
        first=copy.deepcopy(t.resource_failure);t.probe=base_tests.healthy
        with self.assertRaises(h.Blocked):t.safety()
        self.assertEqual(t.resource_failure,first)

    def test_invalid_baseline_type_does_not_mask_first_failure(self):
        base=self.fixture();real=h.Trial
        with patch.object(h,'PagingTelemetry',TelemetryFake):
            t=real(base.r,'sglang',base.c,base.d,base.http,base_tests.healthy,base.root,base_tests.write,
                lambda _:None,operator_sha256=h.SG_SWAP_OPERATOR_SHA)
        t.before=None
        with self.assertRaises(h.Blocked):t.safety()
        self.assertIsNone(t.resource_failure['baseline'])
        self.assertIn('RESOURCE_PROBE_UNAVAILABLE_OR_INVALID',t.resource_failure['reason'])


class TelemetryTests(unittest.TestCase):
    def value(self,n):return {'pswpin':n,'pswpout':2*n,'page_size':4096,'memory_psi':{k:{'avg10':0.0,'total_us':0} for k in ('some','full')}}
    def test_monotonic_actual_rate_and_1hz_bound(self):
        value={'n':0};calls=[]
        def read():calls.append(1);return self.value(value['n'])
        t=PagingTelemetry(read);t.sample(0);value['n']=2;t.sample(.5);t.sample(1.5)
        self.assertEqual(len(calls),2);self.assertEqual(t.snapshot()['samples'][-1]['swap_io_bytes_per_second'],6*4096/1.5)
        for i in range(2,80):t.sample(i)
        self.assertEqual(len(t.snapshot()['samples']),32)
    def test_unavailable_or_counter_reset_is_explicit_not_fabricated_zero(self):
        t=PagingTelemetry(lambda:(_ for _ in ()).throw(OSError('fixture')));t.sample(0)
        self.assertEqual(t.snapshot()['samples'][0]['status'],'UNAVAILABLE')
        self.assertNotIn('swap_io_bytes_per_second',t.snapshot()['samples'][0])
        sequence=iter([self.value(20),self.value(1)]);t=PagingTelemetry(lambda:next(sequence));t.sample(0);t.sample(1)
        self.assertEqual(t.snapshot()['samples'][-1]['status'],'UNAVAILABLE')
        self.assertFalse(t.snapshot()['admission_gate'])


if __name__=='__main__':unittest.main()
