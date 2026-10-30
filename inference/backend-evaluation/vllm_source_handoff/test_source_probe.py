import json
import hashlib
import io
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch
import inspect_vllm_source_host as p


class SourceProbeTests(unittest.TestCase):
    def test_fixed_manifest_contains_seven_critical_sources(self):
        self.assertEqual(len(p.manifest()['files']),7)
        self.assertEqual(p.manifest()['source_commit'],'5df63a7203cdb9328d824a27b682e77c7b9928be')
    def test_cpu_command_has_no_gpu_models_network_or_privileges(self):
        cmds=p.commands(1000,1000,'a'*32);args=cmds[1]
        for bad in ['--device','--gpus','--privileged','--mount','-v','--ipc=host','--security-opt=seccomp=unconfined']:
            self.assertNotIn(bad,args)
        self.assertIn('--pull=never',args);self.assertEqual(args[args.index('--network')+1],'none')
        self.assertEqual(args[args.index('--memory')+1],'256m');self.assertEqual(args[args.index('--memory-swap')+1],'256m')
        self.assertIn(p.IMAGE,args);self.assertEqual(args[args.index('--user')+1],'1000:1000')
    def test_probe_compiles_and_never_imports_gpu_libraries(self):
        text=p.probe_text();compile(text,'<fixed-cpu-probe>','exec')
        for bad in ['import torch','import vllm','import triton','subprocess','exec(']:self.assertNotIn(bad,text)
    def test_fixed_identity_requires_digest_platform_and_image_id(self):
        row={'RepoDigests':[p.IMAGE],'Architecture':'amd64','Os':'linux','Id':'sha256:'+'1'*64,'Size':123}
        self.assertEqual(p.verify_image([row])['size'],123)
        for key,value in [('RepoDigests',[]),('Architecture','arm64'),('Id','mutable')]:
            changed={**row,key:value}
            with self.assertRaises(ValueError):p.verify_image([changed])
    def test_no_human_flag_performs_no_subprocess(self):
        with patch('sys.argv',['inspect']),patch.object(p.subprocess,'run') as run,patch('builtins.print'):
            self.assertEqual(p.main(),0);run.assert_not_called()
    def test_fake_distribution_reads_hashes_without_import_and_redacts_private_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'vllm').mkdir();source=root/'vllm/fixed.py';source.write_bytes(b'never executed')
            expected={'source_commit':'5df63a7203cdb9328d824a27b682e77c7b9928be','files':[{'path':'vllm/fixed.py','bytes':14,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
            direct={'url':'https://user:secret@example.invalid/private','vcs_info':{'commit_id':expected['source_commit']}}
            dist=SimpleNamespace(locate_file=lambda name:root/name,files=['vllm/_C.so'],read_text=lambda _:json.dumps(direct))
            output=io.StringIO()
            with patch('importlib.metadata.distribution',return_value=dist),patch('importlib.metadata.version',return_value='fixture'),redirect_stdout(output):
                exec(p.PROBE_PREFIX+repr(expected)+'\n'+p.PROBE_BODY,{})
            data=json.loads(output.getvalue())
            self.assertTrue(data['all_critical_source_files_match']);self.assertFalse(data['reported_commit_matches'])
            self.assertNotIn('secret',output.getvalue());self.assertNotIn('example.invalid',output.getvalue())
            self.assertEqual(data['generation_requests'],0)
    def test_missing_source_does_not_become_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);expected={'source_commit':'a'*40,'files':[{'path':'vllm/missing.py','bytes':1,'sha256':'0'*64}]}
            dist=SimpleNamespace(locate_file=lambda name:root/name,files=[],read_text=lambda _:'{}')
            output=io.StringIO()
            with patch('importlib.metadata.distribution',return_value=dist),patch('importlib.metadata.version',return_value='fixture'),redirect_stdout(output):
                exec(p.PROBE_PREFIX+repr(expected)+'\n'+p.PROBE_BODY,{})
            self.assertFalse(json.loads(output.getvalue())['all_critical_source_files_match'])
    def test_arbitrary_names_rejected(self):
        with self.assertRaises(ValueError):p.commands(1000,1000,'x; arbitrary')


if __name__=='__main__':unittest.main()
