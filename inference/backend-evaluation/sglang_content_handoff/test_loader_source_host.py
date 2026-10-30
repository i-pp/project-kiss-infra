import io
import json
import sys
import tempfile
from pathlib import Path
from contextlib import redirect_stdout,contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import inspect_loader_source_host as h


def data():return {'status':'STATIC_SOURCE_ONLY_NO_BACKEND_IMPORT','source_executions':0,'gpu_operations':0,
    'generation_requests':0,'files':{n:{'status':'UNAVAILABLE','error_class':'fixture'} for n in h.EXPECTED_FILES}}


class HostSourceTests(unittest.TestCase):
    def test_default_no_container_or_guard(self):
        with patch.object(sys,'argv',['inspect']),patch.object(h.base,'installed_guard',side_effect=AssertionError('no host')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(h.main(),0)
        self.assertIn('PREPARED_STATIC_SOURCE_READ_ONLY',out.getvalue())
    def test_response_rejects_any_execution_or_foreign_path(self):
        for mutate in [lambda d:d.update(gpu_operations=1),lambda d:d['files'].update({'/foreign':{}})]:
            value=data();mutate(value)
            with self.assertRaises(ValueError):h.validate(value)
    def run_fake(self,remaining=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);repo=Path(tmp.name)/'repo';repo.mkdir()
        calls=[]
        def directory(path):path.mkdir(parents=True,mode=0o700,exist_ok=True);return path
        def write(path,value):path.write_text(json.dumps(value));path.chmod(0o600)
        class Client:
            def __init__(self,**kwargs):pass
            @contextmanager
            def locked(self):yield
        def invoke(argv,payload,timeout,guard):
            calls.append(argv);guard()
            if len(calls)==1:return 0,json.dumps([{'RepoDigests':[h.base.IMAGE],'Architecture':'amd64','Os':'linux','Id':'sha256:'+'b'*64,'Config':{}}]),''
            if len(calls)==2:
                self.assertNotIn('--device',argv);self.assertIn('none',argv);self.assertIn('-S',argv)
                self.assertIn('source_executions',payload);return 0,json.dumps(data()),''
            return 0,('b'*64 if remaining else ''),''
        with patch.object(sys,'argv',['inspect','--inspect-human']),patch.object(h.base,'installed_guard',return_value=(repo,lambda:None,directory,write)),patch.object(h.base,'invoke',side_effect=invoke),patch.dict(sys.modules,{'local_llm':SimpleNamespace(Client=Client)}),redirect_stdout(io.StringIO()):
            code=h.main()
        return repo,calls,code
    def test_cpu_only_source_receipt_and_confirmed_absence(self):
        repo,calls,code=self.run_fake();self.assertEqual(code,0);self.assertEqual(len(calls),3)
        receipts=list(repo.glob('agents/local_llm/.runtime/backend-runtime/loader-source-inspection/run-*/receipt.json'))
        self.assertEqual(len(receipts),1);receipt=json.loads(receipts[0].read_text())
        self.assertTrue(receipt['cpu_container_absence_confirmed']);self.assertFalse(receipt['gpu_device_access'])
    def test_unconfirmed_cpu_absence_writes_specific_no_retry_marker(self):
        repo,calls,code=self.run_fake(True);self.assertEqual(code,1)
        self.assertTrue((repo/'agents/local_llm/.runtime/backend-runtime/loader-source-inspection/UNCERTAIN.json').exists())
        self.assertEqual(len(calls),3)


if __name__=='__main__':unittest.main()
