"""Offline profile/receipt/cleanup regressions; no native or model execution."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from contextlib import redirect_stdout
import tempfile
import unittest
from unittest.mock import patch
import host_api_trial as h
import test_host_api_trial as f


def retry_review():
    return {'aiter_cache_profile':h.AITER_PROFILE,
            'aiter_cache_retry_authorization':h.AITER_RETRY_APPROVAL,
            'aiter_cache_retry_max_attempts':1,'aiter_source_receipt_sha256':h.AITER_RECEIPT_SHA}


class AITERProfileTests(unittest.TestCase):
    def test_env_only_new_profile_sglang_before_process_start(self):
        r={'review':retry_review()}
        self.assertEqual(h.server_environment('sglang',r)['AITER_JIT_DIR'],'/jit-cache/aiter')
        self.assertEqual(h.server_environment('sglang',r)['TRITON_CACHE_DIR'],'/jit-cache/triton')
        self.assertNotIn('AITER_JIT_DIR',h.server_environment('sglang'))
        self.assertNotIn('AITER_JIT_DIR',h.server_environment('vllm',r))
        self.assertEqual(h.server_environment('sglang',r)['TMPDIR'],'/tmp')
    def test_profile_gate_rejects_wrong_backend_digest_or_review(self):
        r={'review':retry_review()}
        for backend,digest in [('vllm',h.AITER_RETRY_OPERATOR_SHA),('sglang',h.SG_SWAP_OPERATOR_SHA)]:
            with self.assertRaises(h.Blocked):h.validate_aiter_retry(r,backend,digest)
        for k,v in [('aiter_cache_retry_max_attempts',2),('aiter_source_receipt_sha256','0'*64),('aiter_cache_retry_authorization','other')]:
            bad=copy.deepcopy(r);bad['review'][k]=v
            with self.assertRaises(h.Blocked):h.validate_aiter_retry(bad,'sglang',h.AITER_RETRY_OPERATOR_SHA)
        self.assertIsNone(h.validate_aiter_retry({'review':{}},'vllm','a'*64))
    def test_private_receipt_is_required_and_bound_to_fixed_image(self):
        r={'project_root':'/fixture','review':retry_review(),'runtimes':{'sglang':{'image_ref':'fixed'}}}
        receipt={'status':'STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS',
                 'cpu_container_absence_confirmed':True,'generation_requests':0,'gpu_device_access':False,'image':'fixed'}
        with patch.object(h,'private_read',return_value=receipt) as read:
            out=h.validate_aiter_retry(r,'sglang',h.AITER_RETRY_OPERATOR_SHA)
            self.assertEqual(out['shared_exec_tmpfs_bytes'],512<<20)
            read.assert_called_once_with(Path('/fixture')/h.AITER_RECEIPT_RELATIVE,h.AITER_RECEIPT_SHA)
        for field,bad in [('cpu_container_absence_confirmed',False),('gpu_device_access',True),('image','other'),('generation_requests',1)]:
            altered={**receipt,field:bad}
            with patch.object(h,'private_read',return_value=altered),self.assertRaises(h.Blocked):
                h.validate_aiter_retry(r,'sglang',h.AITER_RETRY_OPERATOR_SHA)
        with patch.object(h,'private_read',side_effect=h.Blocked('OPERATOR_JSON_DIGEST_MISMATCH')),self.assertRaises(h.Blocked):
            h.validate_aiter_retry(r,'sglang',h.AITER_RETRY_OPERATOR_SHA)
    def test_created_environment_and_contract_reject_wrong_or_duplicate_cache(self):
        with tempfile.TemporaryDirectory() as t:
            r=f.record(Path(t));r['review'].update(retry_review());driver=f.Driver()
            ident={'name':'fixed','token':'fixture','owner':str(os.getuid()),'cid':None}
            driver.create(ident,r,'sglang');row=driver.row
            row['Config']['Env']=[k+'='+v for k,v in h.server_environment('sglang',r).items()]
            h.verify_container_contract(row,r,'sglang')
            for extra in ['AITER_JIT_DIR=/tmp/aiter','AITER_JIT_DIR=/jit-cache/aiter']:
                bad=copy.deepcopy(row);bad['Config']['Env'].append(extra)
                with self.assertRaisesRegex(h.Blocked,'STARTUP_ENVIRONMENT'):h.verify_container_contract(bad,r,'sglang')
            bad=copy.deepcopy(row);bad['HostConfig']['Tmpfs']['/jit-cache']=bad['HostConfig']['Tmpfs']['/jit-cache'].replace('512m','1g')
            with self.assertRaises(h.Blocked):h.verify_container_contract(bad,r,'sglang')
    def test_new_attempt_single_post_cleanup_restore_and_no_rebaseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=f.record(root);r['review'].update(retry_review());run=root/'run';run.mkdir()
            class D(f.Driver):
                def create(self,ident,rec,backend):
                    cid=super().create(ident,rec,backend)
                    self.row['Config']['Env']=[k+'='+v for k,v in h.server_environment(backend,rec).items()]
                    return cid
            c=f.Coordinator();d=D();http=f.HTTP();clock=f.Clock();reserved=[]
            t=h.Trial(r,'sglang',c,d,http,f.healthy,run,f.write,
                      lambda _:{'system':'COMMON POLICY FIXTURE','metadata':{'sha256':'fixture'}},verify=lambda _,**kw:[],unchanged=lambda _:True,
                      clock=clock.now,sleep=clock.sleep,network_profile={'name':h.NETWORK,'id':'c'*64},
                      reserve_attempt=lambda:reserved.append(1),operator_sha256=h.AITER_RETRY_OPERATOR_SHA)
            with redirect_stdout(io.StringIO()):out=t.execute()
            self.assertEqual(out['status'],'COMPLETED',out);self.assertEqual(http.posts,1)
            self.assertEqual(reserved,[1]);self.assertEqual(c.events.count('restore'),1);self.assertIsNone(d.row)
            policy=json.loads((run/'resource-policy.json').read_text())
            self.assertEqual(policy['operator_scope_sha256'],h.AITER_RETRY_OPERATOR_SHA)
            self.assertEqual(policy['swap_growth_limit_bytes'],128<<20)
            self.assertFalse(policy['baseline_reset_after_assets'])
    def test_old_attempt_not_reused_or_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=h.approved_attempt_path(root,'sglang',h.SG_SWAP_OPERATOR_SHA)
            h.reserve_approved_attempt(root,'sglang',h.SG_SWAP_OPERATOR_SHA,root/'old')
            before=old.read_bytes();h.reserve_approved_attempt(root,'sglang',h.AITER_RETRY_OPERATOR_SHA,root/'new')
            self.assertEqual(old.read_bytes(),before)
            with self.assertRaises(FileExistsError):h.reserve_approved_attempt(root,'sglang',h.AITER_RETRY_OPERATOR_SHA,root/'again')


if __name__=='__main__':unittest.main()
