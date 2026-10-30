import copy,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import saved_loader_evidence as e

class SavedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'inference/backend-evaluation/sglang_content_handoff').mkdir(parents=True)
        self.trials=self.root/'agents/local_llm/.runtime/backend-api-trials';self.trials.mkdir(parents=True)
        self.record={'project_root':str(self.root),'runtimes':{'sglang':{'image_ref':'fixed','image_id':'sha256:fixed'}}}
        self.receipt={'status':'STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS','image':'fixed','identity':{'image_id':'sha256:fixed'},'cpu_container_absence_confirmed':True,'gpu_device_access':False,'generation_requests':0,'result':{}}
        self.old={'environment':'NOT_RUN','generation_requests':0,'generation_request_intents':0,'restoration':'NOT_NEEDED','cleanup_confirmed':True}
        self.intent={'run':str(self.root/e.RUN_REL)};self.driver=SimpleNamespace(image=lambda _:{'Id':'sha256:fixed','Config':{}})
    def check(self):
        def read(path,digest):
            if digest==e.RECEIPT_SHA:return self.receipt
            if digest==e.SUMMARY_SHA:return self.old
            if digest==e.PREFLIGHT_SHA:return self.intent
            raise AssertionError('No arbitrary evidence read')
        modules={'inspect_loader_source_host':SimpleNamespace(validate=lambda d:d),'loader_static_gate':SimpleNamespace(confirm=lambda d:{'source_sha256':{'fixture':'hash'}})}
        with patch.object(e,'private_read',side_effect=read),patch.dict(sys.modules,modules):return e.validate(self.record,self.driver)
    def test_reuse_requires_fresh_exact_image_id(self):
        self.assertEqual(self.check()['current_image_id'],'sha256:fixed')
        self.driver.image=lambda _:{'Id':'sha256:other','Config':{}}
        with self.assertRaisesRegex(e.Blocked,'CURRENT_IMAGE'):self.check()
    def test_changed_capture_identity_absence_or_prior_lifecycle_rejected(self):
        for target,field,bad in [(self.receipt,'cpu_container_absence_confirmed',False),(self.receipt,'image','other'),(self.old,'generation_request_intents',1),(self.old,'restoration',{'status':'RESTORED'})]:
            old=target[field];target[field]=bad
            with self.assertRaises(e.Blocked):self.check()
            target[field]=old
    def test_consumed_attempt_or_uncertain_stops_without_inspection(self):
        for marker in [self.trials/('attempt-sglang-'+e.OPERATOR+'.json'),self.root/'agents/local_llm/.runtime/UNCERTAIN.json']:
            marker.write_text('{}')
            with self.assertRaisesRegex(e.Blocked,'CONSUMED_OR_UNCERTAIN'):self.check()
            marker.unlink()
    def test_original_intent_must_bind_exact_prior_run(self):
        self.intent['run']='/foreign'
        with self.assertRaisesRegex(e.Blocked,'PRIOR_ZERO'):self.check()

if __name__=='__main__':unittest.main()
