import copy,unittest
from total_swap_limits import TotalSwapLimits,LimitBlocked,GIB,USER_TOTAL_LIMIT

def value(used=500_000_000,total=64*GIB):return {'mem_available':48*GIB,'gpu_used':22*GIB,'swap_total':total,'swap_free':total-used,'swap_used':used,'boot_id':'fixture'}

class TotalSwapTests(unittest.TestCase):
    def test_absolute_decimal_limit_not_growth_or_gib(self):
        budget=TotalSwapLimits(value());budget.check(value(USER_TOTAL_LIMIT))
        budget.check(value(7_000_000_000))  # growth far above old128MiB is explicitly allowed
        with self.assertRaisesRegex(LimitBlocked,'ABOVE_AUTHORIZED'):budget.check(value(USER_TOTAL_LIMIT+1))
        with self.assertRaises(LimitBlocked):budget.check(value(8*GIB))
        self.assertEqual(budget.policy()['effective_total_used_limit_bytes'],8_000_000_000)
    def test_initial_over_cap_is_blocked_before_work(self):
        baseline=value(8_000_000_001);b=TotalSwapLimits(baseline)
        with self.assertRaises(LimitBlocked):b.check(baseline,start=True)
    def test_actual_smaller_capacity_clamps_cap_and_exhaustion_stops(self):
        b=TotalSwapLimits(value(1,4*GIB));self.assertEqual(b.cap,4*GIB);b.check(value(4*GIB-1,4*GIB))
        with self.assertRaisesRegex(LimitBlocked,'EXHAUSTED'):b.check(value(4*GIB,4*GIB))
    def test_zero_capacity_never_creates_swap(self):
        b=TotalSwapLimits(value(0,0))
        with self.assertRaisesRegex(LimitBlocked,'NO_CONFIGURED_SWAP'):b.check(value(0,0))
    def test_capacity_boot_and_incoherent_or_missing_counters_stop(self):
        for altered in [value(1,63*GIB),{**value(),'boot_id':'changed'},{**value(),'swap_free':1},{**value(),'gpu_used':None},{**value(),'swap_total':False}]:
            with self.assertRaises(LimitBlocked):TotalSwapLimits(value()).check(altered)
    def test_ram_gpu_start_and_continue_guards_are_preserved(self):
        b=TotalSwapLimits(value())
        for start,changes in [(True,{'mem_available':23*GIB}),(False,{'mem_available':16*GIB}),(False,{'gpu_used':59*GIB})]:
            with self.assertRaises(LimitBlocked):b.check({**value(),**changes},start=start)
    def test_baseline_immutable_and_capacity_never_rebased(self):
        b=TotalSwapLimits(value());before=b.baseline;b.baseline['swap_used']=7_000_000_000
        b.check(value(3_000_000_000));self.assertEqual(b.baseline,before)

if __name__=='__main__':unittest.main()
