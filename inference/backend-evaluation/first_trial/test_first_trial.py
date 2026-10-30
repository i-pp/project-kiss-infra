import copy
import json
from pathlib import Path
import unittest
from validate_first_trial import validate


class FirstTrialTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parent
        self.plan=json.loads((root/'first-trial.json').read_text())
        self.config=json.loads((root/'strata-host-config.EXAMPLE.json').read_text())
    def test_validated_plan_is_not_execution_authorization(self):
        result=validate(self.plan,self.config)
        self.assertFalse(result['execution_allowed']);self.assertEqual(result['actual_generations'],0)
    def test_different_source_or_model_is_rejected(self):
        for key,value in [('profile','gpt-oss-120b'),('source_commit','main')]:
            data=copy.deepcopy(self.plan);data[key]=value
            with self.assertRaises(ValueError):validate(data,self.config)
    def test_binary_and_download_identity_are_pinned(self):
        for key,value in [('sha256','0'*64),('bytes',0),('url','https://other.invalid/runtime')]:
            data=copy.deepcopy(self.plan);data['engine'][key]=value
            with self.assertRaises(ValueError):validate(data,self.config)
    def test_extra_hook_or_auto_prefill_is_rejected(self):
        data=copy.deepcopy(self.config);data['before_load']=['arbitrary-command']
        with self.assertRaises(ValueError):validate(self.plan,data)
        data=copy.deepcopy(self.config);data['args'][-1]='auto:512'
        with self.assertRaises(ValueError):validate(self.plan,data)
    def test_cap_increase_and_bypass_are_rejected(self):
        for key in self.plan['prohibited']:
            data=copy.deepcopy(self.plan);data['prohibited'][key]=False
            with self.assertRaises(ValueError):validate(data,self.config)
    def test_repeat_generation_or_false_memory_guarantee_is_rejected(self):
        for key,value in [('max_generations',2),('generation_retries',1),('hard_memory_guarantee',True),('global_gpu_max_gib',64)]:
            data=copy.deepcopy(self.plan);data['budget'][key]=value
            with self.assertRaises(ValueError):validate(data,self.config)


if __name__=='__main__':unittest.main()
