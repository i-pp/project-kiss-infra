import unittest
from sglang_prepare import evaluate,GIB,PROFILES

GOOD={'weight_format':'safetensors_fp8','checkpoint_present':True,'runtime_verified':True,
      'native_gpu_access':True,'rdna_kernels_verified':True,'projected_min_available_ram_bytes':32*GIB,
      'projected_peak_gpu_bytes':50*GIB,'immutable_runtime_ref':'sha256:'+'a'*64}


class PlanningGateTests(unittest.TestCase):
    def test_existing_assets_cannot_be_mistaken_for_pass(self):
        for profile in PROFILES:
            result=evaluate(profile)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertIn('GGUF_HIP_UNSUPPORTED',result['blockers'])
            self.assertFalse(result['execution_allowed']);self.assertEqual(result['generation_count'],0)
    def test_gguf_is_not_unblocked_by_deployment_or_memory(self):
        for profile in PROFILES:
            result=evaluate(profile,{**GOOD,'weight_format':'gguf'})
            self.assertIn('GGUF_HIP_UNSUPPORTED',result['blockers'])
            self.assertIsNone(result['launch_draft'])
    def test_mxfp4_checkpoint_does_not_bypass_rdna_kernel_limit(self):
        result=evaluate('gpt-oss-120b',{**GOOD,'weight_format':'safetensors_mxfp4'})
        self.assertIn('MXFP4_REQUIRES_CDNA_NOT_GFX1151',result['blockers'])
    def test_no_gpu_route_blocks_even_an_available_checkpoint(self):
        result=evaluate('qwen-coder-next',{**GOOD,'native_gpu_access':False})
        self.assertIn('NO_AUTHORIZED_GPU_EXECUTION_PATH',result['blockers'])
    def test_unverified_memory_or_kernel_is_not_launch_ready(self):
        for extra in [{'projected_min_available_ram_bytes':23*GIB},
                      {'projected_peak_gpu_bytes':59*GIB},
                      {'projected_peak_gpu_bytes':True},
                      {'rdna_kernels_verified':False},
                      {'immutable_runtime_ref':'latest'}]:
            self.assertEqual(evaluate('qwen-coder-next',{**GOOD,**extra})['status'],'BLOCKED')
    def test_even_complete_prerequisites_only_produce_review_draft(self):
        result=evaluate('qwen-coder-next',GOOD)
        self.assertEqual(result['status'],'READY_FOR_MANUAL_REVIEW')
        self.assertFalse(result['execution_allowed'])
        self.assertEqual(result['environment_verdict'],'NOT_RUN')
        self.assertEqual(result['model_quality_verdict'],'UNASSESSED')
    def test_arbitrary_target_or_remote_code_authority_is_rejected(self):
        for profile in ['http://example.invalid','other-model']:
            with self.assertRaises(ValueError):evaluate(profile)
        for extra in [{'command':'anything'},{'url':'http://example.invalid'},{'trust_remote_code':True}]:
            with self.assertRaises(ValueError):evaluate('qwen-coder-next',{**GOOD,**extra})


if __name__=='__main__':unittest.main()
