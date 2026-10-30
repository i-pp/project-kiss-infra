import copy,io,json,os,sys,tempfile,unittest
from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
import host_api_trial as h
import test_host_api_trial as f

class SequentialPreflightTests(unittest.TestCase):
    def test_incompatible_static_source_never_unloads_or_creates_trial_and_cannot_blind_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record=f.record(root);c=f.Coordinator();calls=[]
            def directory(path):path.mkdir(parents=True,exist_ok=True);return path
            def capture(_):calls.append(1);raise ValueError('SEQUENTIAL_LOADER_OPTION_NOT_CONFIRMED')
            argv=['trial','--run-human-approved','--backend','sglang','--operator-json','unused','--operator-sha256',h.SEQUENTIAL_OPERATOR_SHA]
            with patch.object(sys,'argv',argv),patch.object(sys.stdin,'isatty',return_value=True),patch.object(h,'install_sigterm_handler'),patch.object(h,'operator_record',return_value=record),patch.object(h,'validate_aiter_retry',return_value=None),patch.object(h,'helpers',return_value=(lambda *a:c,directory,f.write,f.healthy)),patch.object(h,'loader_static_preflight',side_effect=capture),patch.object(h,'Trial',side_effect=AssertionError('No model trial before static PASS')),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'NOT_CONFIRMED'):h.main()
                with self.assertRaises(FileExistsError):h.main()
            self.assertEqual(calls,[1]);self.assertNotIn('unload',c.events)
            r=Path(record['project_root'])/'agents/local_llm/.runtime/backend-api-trials'
            self.assertFalse(h.approved_attempt_path(r,'sglang',h.SEQUENTIAL_OPERATOR_SHA).exists())
    def test_cpu_absence_is_required_before_positive_feature_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'inference/backend-evaluation/sglang_content_handoff';folder.mkdir(parents=True)
            receipt=root/'receipt.json';record={'project_root':str(root),'runtimes':{'sglang':{'image_ref':'fixed'}}}
            data={'status':'STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS','cpu_container_absence_confirmed':False,
                  'image':'fixed','generation_requests':0,'gpu_device_access':False,'result':{}}
            receipt.write_text(json.dumps(data));receipt.chmod(0o600);gate=[]
            modules={'inspect_loader_source_host':SimpleNamespace(capture_once=lambda:receipt),'loader_static_gate':SimpleNamespace(confirm=lambda d:gate.append(d) or {'status':'PASS'})}
            with patch.dict(sys.modules,modules):
                with self.assertRaisesRegex(h.Blocked,'NOT_CONFIRMED'):h.loader_static_preflight(record)
                self.assertEqual(gate,[])
                data['cpu_container_absence_confirmed']=True;receipt.write_text(json.dumps(data));result=h.loader_static_preflight(record)
                self.assertEqual(result['status'],'PASS');self.assertEqual(gate,[{}]);self.assertEqual(len(result['receipt_sha256']),64)
    def test_sequential_profile_authorization_cannot_use_old_operator_digest(self):
        review={'aiter_cache_profile':h.AITER_PROFILE,'aiter_cache_retry_authorization':h.AITER_RETRY_APPROVAL,
                'aiter_cache_retry_max_attempts':1,'aiter_source_receipt_sha256':h.AITER_RECEIPT_SHA,
                'sglang_sequential_loader_profile':'one-thread-v1','sglang_sequential_loader_authorization':h.SEQUENTIAL_APPROVAL,
                'sglang_sequential_loader_max_attempts':1}
        for digest in [h.AITER_RETRY_OPERATOR_SHA,h.SG_SWAP_OPERATOR_SHA]:
            with self.assertRaises(h.Blocked):h.validate_aiter_retry({'review':review},'sglang',digest)
        altered=copy.deepcopy(review);altered['sglang_sequential_loader_max_attempts']=2
        with self.assertRaises(h.Blocked):h.validate_aiter_retry({'review':altered},'sglang',h.SEQUENTIAL_OPERATOR_SHA)

if __name__=='__main__':unittest.main()
