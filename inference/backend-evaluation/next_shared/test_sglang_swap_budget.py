import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).with_name('sglang_swap_budget.py')
spec=importlib.util.spec_from_file_location('sg_swap_proposal',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class BudgetTests(unittest.TestCase):
    def setUp(self):self.before={'mem_available':45*m.GIB,'gpu_used':21*m.GIB,'swap_used':581632}
    def test_existing_swap_and_observed_host_drift_are_not_zero_requirement(self):
        b=m.SGLangBudget(self.before);proof=b.observe({**self.before,'swap_used':3051520})
        self.assertEqual(proof['swap_growth_bytes'],2469888)
    def test_boundary128mib_is_finite_and_next_page_stops(self):
        b=m.SGLangBudget(self.before)
        b.observe({**self.before,'swap_used':self.before['swap_used']+m.MAX_GROWTH})
        with self.assertRaises(m.BudgetBlocked) as failure:b.observe({**self.before,'swap_used':self.before['swap_used']+m.MAX_GROWTH+4096})
        self.assertEqual(failure.exception.resource_evidence['swap_growth_limit_bytes'],128<<20)
    def test_baseline_is_never_reset_after_hash_or_reclaim(self):
        b=m.SGLangBudget(self.before)
        b.observe({**self.before,'swap_used':self.before['swap_used']+100*(1<<20)})
        b.observe({**self.before,'swap_used':0})
        with self.assertRaises(m.BudgetBlocked):b.observe({**self.before,'swap_used':self.before['swap_used']+129*(1<<20)})
        self.assertEqual(b.baseline,self.before)
    def test_ram24_start_and16_continue_limits_unchanged(self):
        for value,start in [(24*m.GIB-1,True),(16*m.GIB,False)]:
            b=m.SGLangBudget(self.before)
            with self.subTest(value=value),self.assertRaises(m.BudgetBlocked):b.observe({**self.before,'mem_available':value},start=start)
        m.SGLangBudget({**self.before,'mem_available':24*m.GIB})
    def test_gpu_limit_unchanged(self):
        b=m.SGLangBudget(self.before)
        with self.assertRaises(m.BudgetBlocked):b.observe({**self.before,'gpu_used':58*m.GIB+1})
    def test_missing_invalid_values_fail_closed(self):
        for key,value in [('gpu_used',None),('swap_used',True),('mem_available',-1)]:
            with self.subTest(key=key),self.assertRaises(m.BudgetBlocked):m.SGLangBudget({**self.before,key:value})
    def test_first_bad_snapshot_not_overwritten_by_followup_probe(self):
        b=m.SGLangBudget(self.before)
        with self.assertRaises(m.BudgetBlocked) as failure:b.observe({**self.before,'swap_used':self.before['swap_used']+m.MAX_GROWTH+1})
        recorded=failure.exception.resource_evidence['observed']['swap_used']
        with self.assertRaises(m.BudgetBlocked) as repeated:b.observe(self.before)
        self.assertIs(repeated.exception,failure.exception)
        self.assertEqual(failure.exception.resource_evidence['observed']['swap_used'],recorded)


if __name__=='__main__':unittest.main()
