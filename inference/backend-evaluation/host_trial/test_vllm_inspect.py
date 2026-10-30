import unittest
from inspect_vllm_host import commands,IMAGE,PROBE


class MetadataTests(unittest.TestCase):
    def test_fixed_existing_image_cpu_only_no_mounts_or_gpu(self):
        inspect,run=commands(1000,1000,'a'*32)
        self.assertIn(IMAGE,inspect);self.assertIn(IMAGE,run)
        for forbidden in ['--gpus','--device','--privileged','--volume','--mount','--publish']:
            self.assertNotIn(forbidden,run)
        self.assertIn('none',run);self.assertIn('never',run);self.assertIn('no-new-privileges:true',run)
        self.assertNotIn('import torch',PROBE);self.assertNotIn('import vllm',PROBE)
    def test_token_cannot_inject_command(self):
        with self.assertRaises(ValueError):commands(1000,1000,';anything')


if __name__=='__main__':unittest.main()
