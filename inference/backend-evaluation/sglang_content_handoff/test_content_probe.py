"""CPU fakes only; no real subprocess, Docker, package/source import, or GPU."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import inspect_sglang_content_host as p

class Tests(unittest.TestCase):
    def test_fixed_manifest(self):
        d=p.manifest();self.assertEqual(d['source_commit'],p.COMMIT);self.assertEqual(len(d['files']),4)
    def test_probe_no_package_import_and_site_disabled(self):
        text=p.probe_text();compile(text,'<probe>','exec')
        for bad in ['import torch','import sglang','import triton','import aiter','subprocess','exec(','eval(']:self.assertNotIn(bad,text)
        args=p.commands(1000,1000,'1'*32)[1]
        self.assertEqual(args[-4:],['-I','-S','-B','-'])
    def test_fixed_container_hard_limits(self):
        args=p.commands(1000,1000,'1'*32)[1]
        for key,value in [('--network','none'),('--ipc','private'),('--memory','256m'),('--memory-swap','256m'),('--cpus','1'),('--pids-limit','64'),('--user','1000:1000')]:
            self.assertEqual(args[args.index(key)+1],value)
        for flag in ['--read-only','--pull=never','--rm','--no-healthcheck','--cap-drop','--security-opt']:self.assertIn(flag,args)
        for bad in ['--device','--gpus','--privileged','--mount','-v','--ipc=host','--network=host','--security-opt=seccomp=unconfined']:self.assertNotIn(bad,args)
        self.assertEqual(args[args.index('--tmpfs')+1],'/tmp:rw,noexec,nosuid,nodev,size=16m')
    def test_arbitrary_uid_or_name_rejected(self):
        for uid,gid,token in [(0,0,'a'*32),(1000,1000,'arbitrary'),('1000',1000,'b'*32)]:
            with self.assertRaises(ValueError):p.commands(uid,gid,token)
    def test_verify_image_rejects_wrong_digest_platform_and_volumes(self):
        d={'RepoDigests':[p.IMAGE],'Architecture':'amd64','Os':'linux','Id':'sha256:'+'a'*64,'Size':50912606399,'Config':{}}
        self.assertEqual(p.verify_image([d])['size_bytes'],50912606399)
        for key,value in [('RepoDigests',[]),('Architecture','arm64'),('Id','mutable'),('Config',{'Volumes':{'/data':{}}})]:
            with self.subTest(key=key),self.assertRaises(ValueError):p.verify_image([{**d,key:value}])
    def test_fake_source_hashes_and_private_provenance_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'sglang/fixed.py';source.parent.mkdir();source.write_bytes(b'not executed')
            expected={'files':[{'path':'sglang/fixed.py','bytes':12,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
            direct={'url':'https://user:secret@private.invalid/repo','vcs_info':{'commit_id':'a'*40}}
            dist=SimpleNamespace(metadata={'Name':'sglang'},version='0.5.22',read_text=lambda _:json.dumps(direct))
            text=(p.PROBE_PREFIX+repr(expected)+'\n'+p.PROBE_BODY).replace('/sgl-workspace/sglang/python',temp)
            out=io.StringIO()
            with patch('importlib.metadata.distributions',return_value=[dist]),contextlib.redirect_stdout(out):exec(text,{})
            data=json.loads(out.getvalue());self.assertTrue(data['all_selected_source_files_match']);self.assertFalse(data['packages']['sglang']['public_fixed_repo'])
            self.assertNotIn('secret',out.getvalue());self.assertNotIn('private.invalid',out.getvalue());self.assertFalse(data['gpu_package_imports'])
    def test_missing_or_changed_source_fails_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            expected={'files':[{'path':'sglang/missing.py','bytes':12,'sha256':'0'*64}]}
            text=(p.PROBE_PREFIX+repr(expected)+'\n'+p.PROBE_BODY).replace('/sgl-workspace/sglang/python',temp)
            out=io.StringIO()
            with patch('importlib.metadata.distributions',return_value=[]),contextlib.redirect_stdout(out):exec(text,{})
            self.assertFalse(json.loads(out.getvalue())['all_selected_source_files_match'])
    def test_response_cannot_assert_match_without_fixed_sources(self):
        rows=[]
        for item in p.manifest()['files']:
            rows.append({'path':item['path'],'expected_sha256':item['sha256'],'expected_bytes':item['bytes'],
                         'matches':True,'candidates':[{'sha256':item['sha256'],'bytes':item['bytes']}]})
        data={'generation_requests':0,'not_whole_source_attestation':True,'gpu_package_imports':False,
              'source_files':rows,'packages':{},'all_selected_source_files_match':True}
        self.assertIs(p.validate_probe_result(data),data)
        changed=copy.deepcopy(data);changed['source_files'][0]['candidates'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):p.validate_probe_result(changed)
        changed=copy.deepcopy(data);changed['source_files']=[]
        with self.assertRaises(ValueError):p.validate_probe_result(changed)
    def test_no_human_flag_no_docker_or_guard(self):
        with patch.object(p.sys,'argv',['probe']),patch.object(p,'installed_guard',side_effect=AssertionError()),patch.object(p.subprocess,'Popen',side_effect=AssertionError()),patch('builtins.print'):
            self.assertEqual(p.main(),0)
    def test_task_layout_rejected(self):
        with patch.object(p,'ROOT',Path('/tmp/task/sglang-content-handoff')),self.assertRaises(ValueError):p.installed_guard()
    def test_guard_before_subprocess(self):
        with patch.object(p.subprocess,'Popen',side_effect=AssertionError()):
            with self.assertRaisesRegex(ValueError,'blocked'):p.invoke([],None,30,lambda:(_ for _ in ()).throw(ValueError('blocked')))
    def test_interrupt_reaps_cli_only(self):
        class Proc:
            stdin=None;stdout=None;stderr=None;killed=False;reaped=False
            def communicate(self,**kw):raise KeyboardInterrupt()
            def kill(self):self.killed=True
            def wait(self,timeout):self.reaped=True
        proc=Proc()
        with patch.object(p.subprocess,'Popen',return_value=proc),self.assertRaisesRegex(RuntimeError,'REAP_True'):p.invoke([],None,30,lambda:None)
        self.assertTrue(proc.killed and proc.reaped)
    def test_spawn_interrupt_marks_reap_unconfirmed(self):
        with patch.object(p.subprocess,'Popen',side_effect=KeyboardInterrupt()),self.assertRaisesRegex(RuntimeError,'REAP_False'):p.invoke([],None,30,lambda:None)
    def test_sigterm_is_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):p.terminate(15,None)

if __name__=='__main__':unittest.main()
