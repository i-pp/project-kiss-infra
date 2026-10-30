import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import total_swap_resume_evidence as e

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.root=Path('/fixture');self.auth={'authorization':e.AUTHORIZATION,'original_gpu_operator_sha256':e.saved_loader_evidence.OPERATOR,'host_swap_total_used_limit_bytes':8_000_000_000,'new_gpu_allowance':False}
        self.old={'environment':'NOT_RUN','generation_requests':0,'generation_request_intents':0,'restoration':'NOT_NEEDED','cleanup_confirmed':True};self.intent={'run':str(self.root/e.LATEST_RUN)}
    def read(self,path,digest):
        if digest==e.AUTH_SHA:return self.auth
        if digest==e.LATEST_SUMMARY_SHA:return self.old
        if digest==e.RESUME_INTENT_SHA:return self.intent
        raise AssertionError('No other file reads')
    def test_exact_user_limit_and_same_unused_allowance_bound_to_past_zero_run(self):
        with patch.object(e,'private_read',side_effect=self.read),patch.object(e.saved_loader_evidence,'validate',return_value={'current_image_id':'fixed'}) as original:
            out=e.validate({'project_root':str(self.root)},'driver');self.assertFalse(out['new_total_swap_authorization']['new_gpu_allowance']);original.assert_called_once()
    def test_wrong_total_limit_new_allowance_or_lifecycle_claim_rejected(self):
        for target,field,bad in [(self.auth,'host_swap_total_used_limit_bytes',8*(1<<30)),(self.auth,'new_gpu_allowance',True),(self.old,'generation_requests',1),(self.old,'restoration',{'status':'RESTORED'})]:
            old=target[field];target[field]=bad
            with patch.object(e,'private_read',side_effect=self.read),patch.object(e.saved_loader_evidence,'validate',side_effect=AssertionError('no image inspection')),self.assertRaises(e.Blocked):e.validate({'project_root':str(self.root)},'driver')
            target[field]=old
    def test_digest_reader_failure_propagates_without_alternate_path(self):
        with patch.object(e,'private_read',side_effect=e.Blocked('DIGEST')),self.assertRaises(e.Blocked):e.authorization(self.root)

if __name__=='__main__':unittest.main()
