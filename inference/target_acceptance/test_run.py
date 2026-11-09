"""Offline target-boundary tests; no Docker, model, service or large-file I/O."""
import copy,hashlib,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from . import run as m
from inference.aceis_service.core_backends import CoreBackends,NAMES
from inference.aceis_service.core import MODELS

class Tests(unittest.TestCase):
    def obj(self):
        x=m.TargetRun();x.event=Mock();return x
    def provider(self):
        config=json.loads(m.CFG.read_text());p=m.FixedExistingOllama(config,m.CFG)
        fixture=json.loads((m.ROOT/'asset-audit/container-inspect.json').read_text())
        if isinstance(fixture,list):fixture=fixture[0]
        p.backend.docker=Mock(return_value=json.dumps([fixture]));return p,fixture
    def test_provider_create_and_remove_are_always_forbidden(self):
        x=self.obj()
        for action in [x.create_provider,x.remove_provider]:
            with self.assertRaises(m.ServiceError):action()
    def test_fixed_existing_identity_passes_without_name_discovery(self):
        p,f=self.provider();self.assertEqual(p.inspect()['Id'],m.ORIGINAL)
        self.assertEqual(p.backend.docker.call_args.args,('inspect',m.ORIGINAL))
    def test_lost_existing_id_cannot_enter_creation_branch(self):
        p,f=self.provider();p.backend.cid=None;p.backend.start_ollama=Mock()
        with self.assertRaises(m.ServiceError):p.ensure(lambda:None)
        p.backend.start_ollama.assert_not_called();p.backend.docker.assert_not_called()
    def test_existing_extra_accelerator_device_rejected(self):
        p,f=self.provider();f['HostConfig']['Devices'].append({'PathOnHost':'/dev/accel/accel0','PathInContainer':'/dev/accel/accel0','CgroupPermissions':'rwm'});p.backend.docker.return_value=json.dumps([f])
        with self.assertRaises(m.ServiceError):p.inspect()
    def test_existing_unknown_cid_rejected(self):
        p,f=self.provider();f['Id']='b'*64;p.backend.docker.return_value=json.dumps([f])
        with self.assertRaises(m.ServiceError):p.inspect()
    def test_host_inventory_cannot_pull_or_import(self):
        p,f=self.provider()
        for route in ['/api/pull','/api/create','/api/chat','/api/delete']:
            with self.assertRaises(m.ServiceError):p.inventory(route)
        p.backend.docker.assert_not_called()
    def test_ensure_preserves_pinned_id_before_start(self):
        p,f=self.provider();p.backend.start_ollama=Mock();p.inventory=Mock()
        with patch.object(m,'manifest_identity'):p.ensure(lambda:None)
        p.backend.start_ollama.assert_called_once();self.assertEqual(p.backend.cid,m.ORIGINAL);p.inventory.assert_called_once_with('/api/tags')
    def test_core_configuration_is_default_and_bounded(self):
        x=self.obj();x.image='sha256:'+'a'*64
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for n in ['host-runtime','host-state','core-state','core-runtime','tmp']:(root/n).mkdir(mode=0o700)
            with patch.object(m,'RUN',root),patch.object(m,'GracefulCoreStop'):
                c=x.configure_core();core=json.loads((root/'core-config.json').read_text())
            self.assertNotIn('acceptance_ollama_profiles',core);self.assertIn('strata_command',core)
            self.assertEqual(c['core']['memory'],40*2**30);self.assertEqual(c['core']['memory_swap'],40*2**30)
            self.assertEqual(c['core']['nano_cpus'],16*10**9);self.assertEqual(len(c['core']['devices']),2)
            self.assertEqual(c['ollama']['state_dir'],str(m.PROD));self.assertEqual(core['npu_socket'],'/npu-agent/service.sock')
    def test_core_graceful_stop_uses_same_validated_id_only(self):
        x=m.GracefulCoreStop.__new__(m.GracefulCoreStop);cid='c'*64;x.inspect=Mock(return_value=(cid,{'State':{'Running':True}}));x.cli=Mock(side_effect=['',json.dumps([{'State':{'Running':False}}])]);x.validate=Mock()
        x.stop();self.assertEqual(x.cli.call_args_list[0].args,('stop','-t','15',cid));self.assertEqual(x.cli.call_args_list[1].args,('inspect',cid))
    def test_unknown_provider_creation_state_blocks_cleanup(self):
        x=self.obj();x.provider=m.ORIGINAL;x.remove_provider=Mock()
        with self.assertRaises(m.ServiceError):x.cleanup()
        x.remove_provider.assert_not_called()
    def test_oom_diagnostics_do_not_prevent_scoped_stop(self):
        x=self.obj();x.core='c'*64;x.policy={};x.sup=Mock();sup=x.sup;x.stop_provider=Mock()
        guard=Mock();guard.inspect.return_value=('short',{'State':{'Running':False,'OOMKilled':True}})
        with patch.object(m,'GracefulCoreStop',return_value=guard),patch.object(m,'write',side_effect=OSError('full')),patch.object(m.subprocess,'run',side_effect=OSError('logs')),patch.object(m,'physical_idle'),patch.object(m,'docker') as cli:
            with self.assertRaisesRegex(m.ServiceError,'OOM'):x.stop_runtime(1)
        sup.close.assert_called_once();x.stop_provider.assert_called_once();cli.assert_called_once_with('rm','c'*64);self.assertIsNone(x.core)
    def test_default_target_thinking_and_tuning_preserved(self):
        for model,gpu,thinking in [('coder-next',48,False),('gpt-oss-120b',28,'low')]:
            with self.subTest(model=model):
                x=CoreBackends.__new__(CoreBackends);x.models=MODELS;x.requires_flash=True;x.names=dict(NAMES);x.active_model=None;x.start_flash=Mock();x.start_ollama=Mock();x.unload=Mock();x.api=Mock(side_effect=[{'done':True,'done_reason':'stop','message':{'content':'OK'}},{'models':[{'name':'aceis-'+model+':latest'}]}])
                job=SimpleNamespace(model=model,messages=[{'role':'user','content':'OK?'}],max_tokens=128,deadline=time.monotonic()+30)
                out=x.generate(job,lambda:None);body=x.api.call_args_list[0].args[1]
                self.assertEqual(body['think'],thinking);self.assertEqual(body['options']['num_gpu'],gpu);self.assertEqual(body['options']['num_ctx'],8192);self.assertEqual(out['content'],'OK')
    def test_incomplete_payload_audit_rejected_without_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'verification').mkdir();(root/'verification/current-payload-sha256.json').write_text('{"completed":false,"entries":[]}')
            with patch.object(m,'ROOT',root):
                with self.assertRaises(m.ServiceError):m.payload_identity()
    def test_mutated_fixture_rw_is_rejected_before_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in m.FIXTURE_SHA:(root/name).write_bytes((m.FROZEN/name).read_bytes())
            p=root/'host-config.json';doc=json.loads(p.read_text());doc['core']['mounts'][0]['RW']=True;p.write_text(json.dumps(doc))
            x=self.obj();x.image='sha256:'+'a'*64
            with patch.object(m,'FROZEN',root),patch.object(m,'GracefulCoreStop') as guard:
                with self.assertRaisesRegex(m.ServiceError,'pinned'):x.configure_core()
            guard.assert_not_called()
    def test_duplicate_unrelated_audit_rows_rejected_even_if_record_hash_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'verification').mkdir();payload=root/'one';payload.write_bytes(b'x');st=payload.stat()
            row={'path':str(payload),'expected_sha256':hashlib.sha256(b'x').hexdigest(),'actual_sha256':hashlib.sha256(b'x').hexdigest(),'expected_bytes':1,'read_bytes':1,'dev':st.st_dev,'inode':st.st_ino,'mtime_ns':st.st_mtime_ns}
            p=root/'verification/current-payload-sha256.json';p.write_text(json.dumps({'completed':True,'entries':[row]*7}));digest=hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.object(m,'ROOT',root),patch.object(m,'PAYLOAD_AUDIT_SHA',digest):
                with self.assertRaisesRegex(m.ServiceError,'exact unique'):m.payload_identity()
    def test_shard_layout_preserves_exact_source_basenames_and_siblings(self):
        x=self.obj();x.image='sha256:'+'a'*64
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for n in ['host-runtime','host-state','core-state','core-runtime','tmp']:(root/n).mkdir(mode=0o700)
            with patch.object(m,'RUN',root),patch.object(m,'GracefulCoreStop'):
                cfg=x.configure_core();core=json.loads((root/'core-config.json').read_text())
            model_mounts=[a for a in cfg['core']['mounts'] if a['Destination'].startswith('/assets/model/')]
            self.assertEqual(len(model_mounts),2)
            for a in model_mounts:
                self.assertFalse(a['RW']);self.assertEqual(Path(a['Source']).name,Path(a['Destination']).name)
            paths=[]
            for flag in ['--native','--ple-gguf']:
                v=core['strata_command'][core['strata_command'].index(flag)+1];paths.append(v)
                self.assertIn(v,[a['Destination'] for a in model_mounts]);self.assertRegex(v,r'-0000[12]-of-00002\.gguf$')
            self.assertEqual(Path(paths[0]).parent,Path(paths[1]).parent)
    def test_layout_resume_rejects_prior_job_outcome(self):
        rows=[{'stage':'job_submitted'},{'stage':'production_restored'},{'stage':'scheduler_restored'}]
        with patch.object(m,'pinned_json',return_value=rows):
            with self.assertRaisesRegex(m.ServiceError,'no replay'):m.validate_layout_resume()
    def test_layout_resume_requires_restored_prior_window(self):
        with patch.object(m,'pinned_json',return_value=[{'stage':'acceptance_failed'}]):
            with self.assertRaisesRegex(m.ServiceError,'restoration'):m.validate_layout_resume()
if __name__=='__main__':unittest.main()
