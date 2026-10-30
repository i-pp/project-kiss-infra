import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).with_name('stable_swap_policy.py')
spec=importlib.util.spec_from_file_location('swap_proposal',p);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
BOOT='5b850071-086f-43a5-8796-b00537607d8b'


class StableSwapTests(unittest.TestCase):
    def setUp(self):
        self.p=policy.FixedSteadySwap(BOOT,577536)
        self.r={'available_bytes':48*(1<<30),'gpu_used_bytes':21*(1<<30),'swap_used_bytes':577536}
        self.v={'pswpin':0,'pswpout':141}
    def sample(self,t=0,boot=BOOT):self.p.sample(t,boot,self.r,self.v)
    def test_exact_measured_stable_residual_is_evidence_only(self):
        for t in (0,2,4,6,8,10):self.sample(t)
        proof=self.p.finish();self.assertFalse(proof['archive_authorized']);self.assertFalse(proof['generation_authorized'])
    def test_generic_or_over_cap_baseline_refused(self):
        for x in (0,577535,1048576,2*(1<<20),True):
            with self.subTest(x=x),self.assertRaises(policy.PolicyBlocked):policy.FixedSteadySwap(BOOT,x)
    def test_any_swap_change_refused(self):
        self.sample();self.r['swap_used_bytes']+=4096
        with self.assertRaises(policy.PolicyBlocked):self.sample(2)
    def test_swap_io_in_or_out_change_refused(self):
        for key in ('pswpin','pswpout'):
            with self.subTest(key=key):
                self.setUp();self.sample();self.v[key]+=1
                with self.assertRaises(policy.PolicyBlocked):self.sample(2)
    def test_boot_change_refused(self):
        with self.assertRaises(policy.PolicyBlocked):self.sample(0,'other-boot')
    def test_existing_ram_and_gpu_limits_maintained(self):
        for key,value in [('available_bytes',24*(1<<30)-1),('gpu_used_bytes',58*(1<<30)+1)]:
            with self.subTest(key=key):
                self.setUp();self.r[key]=value
                with self.assertRaises(policy.PolicyBlocked):self.sample()
    def test_short_or_missing_proof_refused(self):
        self.sample();self.sample(5)
        with self.assertRaises(policy.PolicyBlocked):self.p.finish()
    def test_replayed_long_gap_or_expired_sample_refused(self):
        self.sample()
        for t in (0,6,31):
            with self.subTest(t=t),self.assertRaises(policy.PolicyBlocked):self.sample(t)
    def test_invalid_probe_values_refused(self):
        for key,value in [('swap_used_bytes',None),('gpu_used_bytes',True),('available_bytes',-1)]:
            with self.subTest(key=key):
                self.setUp();self.r[key]=value
                with self.assertRaises(policy.PolicyBlocked):self.sample()


if __name__=='__main__':unittest.main()
