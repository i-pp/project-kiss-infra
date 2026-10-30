import copy
import json
from pathlib import Path
import unittest
from validate_plan import validate


class PlanTests(unittest.TestCase):
    def setUp(self):self.data=json.loads(Path(__file__).with_name('strata-preparation.json').read_text())
    def test_exact_input_is_reusable_but_not_executable(self):
        result=validate(self.data)
        self.assertTrue(result['input_compatibility_supported'])
        self.assertFalse(result['large_weight_redownload_required'])
        self.assertFalse(result['can_execute'])
    def test_other_architectures_are_not_assumed_supported(self):
        for profile in ('qwen-coder-next','gpt-oss-120b'):
            result=validate(self.data,profile)
            self.assertFalse(result['input_compatibility_supported'])
            self.assertIn('NO_VERIFIED_STRATA_ARCHITECTURE_PATH',result['blockers'])
    def test_different_same_named_shard_is_rejected(self):
        for field,value in [('bytes',1),('sha256','0'*64)]:
            data=copy.deepcopy(self.data);data['weights']['shards'][0][field]=value
            with self.assertRaises(ValueError):validate(data)
    def test_wrong_source_package_or_origin_is_rejected(self):
        for field,value in [('name','other.tar.gz'),('arch','gfx1201'),('url','https://example.invalid/engine')]:
            data=copy.deepcopy(self.data);data['packages'][0][field]=value
            with self.assertRaises(ValueError):validate(data)
    def test_unpinned_source_is_rejected(self):
        self.data['source']['commit']='main'
        with self.assertRaises(ValueError):validate(self.data)
    def test_mtp_or_vision_requires_new_plan(self):
        for key in ('mtp','vision'):
            data=copy.deepcopy(self.data);data['preparation'][key]=True
            with self.assertRaises(ValueError):validate(data)
    def test_no_namespace_or_escalated_host_fallback(self):
        for key in ('namespace_creation_allowed','host_escalated_gpu_execution_allowed'):
            data=copy.deepcopy(self.data);data['environment'][key]=True
            with self.assertRaises(ValueError):validate(data)
    def test_installer_or_claimed_generation_is_not_offline_preparation(self):
        self.data['preparation']['automatic_installer_execution']=True
        with self.assertRaises(ValueError):validate(self.data)
        self.setUp();self.data['scope']['generations']=1
        with self.assertRaises(ValueError):validate(self.data)


if __name__=='__main__':unittest.main()
