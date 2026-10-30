"""Proposal-only offline tests. No new attempt is authorized or started here."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import host_api_trial as h
import test_host_api_trial as f

class SequentialLoaderTests(unittest.TestCase):
    def record(self,root):
        r=f.record(root);r['review']['sglang_sequential_loader_profile']='one-thread-v1';return r
    def test_exact_new_argument_only_changes_selected_sglang_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            r=self.record(Path(temp));old=h.server_argv('sglang');new=h.server_argv('sglang',r)
            self.assertEqual(new[:-2],old)
            self.assertEqual(new[-2],'--model-loader-extra-config')
            self.assertEqual(json.loads(new[-1]),{'enable_multithread_load':False,'num_threads':1})
            self.assertEqual(h.server_argv('vllm',r),h.server_argv('vllm'))
            self.assertEqual(h.STARTUP_SECONDS['sglang'],300);self.assertEqual(h.WHOLE,900)
    def test_create_and_contract_use_same_profile_and_existing_limits(self):
        class Capture(h.Docker):
            def command(self,args,**kw):self.args=args;return 'a'*64
        with tempfile.TemporaryDirectory() as temp:
            r=self.record(Path(temp));driver=Capture(lambda:None)
            with patch.object(h.os,'stat',return_value=SimpleNamespace(st_gid=44)),patch.object(h.os,'getgroups',return_value=[44]):
                driver.create({'name':'fixture','token':'fixture','owner':str(os.getuid())},r,'sglang')
            args=driver.args
            self.assertEqual(args[-2:],[h.server_argv('sglang',r)[-2],h.server_argv('sglang',r)[-1]])
            self.assertEqual(args[args.index('--memory')+1],'32g')
            self.assertEqual(args[args.index('--memory-swap')+1],'32g')
            fake=f.Driver();fake.create({'name':'fixture','token':'fixture','owner':str(os.getuid())},r,'sglang');row=fake.row
            with self.assertRaisesRegex(h.Blocked,'ARGV'):h.verify_container_contract(row,r,'sglang')
            argv=h.server_argv('sglang',r);row['Config']['Entrypoint']=[argv[0]];row['Config']['Cmd']=argv[1:]
            h.verify_container_contract(row,r,'sglang')
    def test_no_reissue_of_previous_attempt_is_permitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);h.reserve_approved_attempt(root,'sglang',h.AITER_RETRY_OPERATOR_SHA,root/'old')
            with self.assertRaises(FileExistsError):h.reserve_approved_attempt(root,'sglang',h.AITER_RETRY_OPERATOR_SHA,root/'again')

if __name__=='__main__':unittest.main()
