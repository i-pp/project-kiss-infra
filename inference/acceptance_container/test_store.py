"""Safe local artifact fixtures, no Docker, HTTP or real model operations."""
import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from . import run as m
from .engine import fixed_engine_identity

def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.provider=self.root/'provider';self.provider.mkdir(mode=0o700);self.store=self.provider/'store';self.store.mkdir(mode=0o700)
        self.config=b'config';self.weight=b'known-model-fixture'
        self.manifest={'schemaVersion':2,'config':{'digest':sha(self.config),'size':len(self.config)},'layers':[{'digest':sha(self.weight),'size':len(self.weight)}]}
        self.raw=json.dumps(self.manifest,separators=(',',':')).encode();self.md=sha(self.raw)
        self.rows=[{'id':'test-fixture','source':'https://registry.ollama.ai/v2/library/fixture/manifests/exact','digest':self.md,'manifest':self.manifest,'raw_bytes':len(self.raw)}]
        (self.store/'blobs').mkdir()
        for blob in [self.config,self.weight,self.raw]:(self.store/'blobs'/sha(blob).replace(':','-')).write_bytes(blob)
        self.link=self.store/'manifests-v2/ollama.com/library/fixture/exact';self.link.parent.mkdir(parents=True);self.link.symlink_to('../../../../blobs/'+self.md.replace(':','-'))
        self.patch=patch.object(m,'PROVIDER',self.provider);self.patch.start()
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def test_exact_manifest_link_and_every_blob_hash_pass(self):
        out=m.store_snapshot(self.rows);self.assertEqual(out['files'][str(self.link.relative_to(self.store))]['type'],'verified_manifest_symlink')
    def test_wrong_manifest_link_target_rejected(self):
        self.link.unlink();self.link.symlink_to('/tmp/unrelated')
        with self.assertRaisesRegex(m.ServiceError,'symlink'):m.store_snapshot(self.rows)
    def test_unknown_directory_symlink_not_followed_or_skipped(self):
        (self.store/'unexpected-dir').symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(m.ServiceError,'symlink'):m.store_snapshot(self.rows)
    def test_missing_expected_link_rejected(self):
        self.link.unlink()
        with self.assertRaisesRegex(m.ServiceError,'absent'):m.store_snapshot(self.rows)
    def test_regular_file_cannot_replace_expected_manifest_symlink(self):
        self.link.unlink();self.link.write_bytes(b'arbitrary substitute')
        with self.assertRaisesRegex(m.ServiceError,'wrong type'):m.store_snapshot(self.rows)
    def test_blob_tamper_rejected(self):
        (self.store/'blobs'/sha(self.weight).replace(':','-')).write_bytes(b'wrong')
        with self.assertRaisesRegex(m.ServiceError,'identity/size'):m.store_snapshot(self.rows)
    def test_hardlink_rejected(self):
        os.link(self.store/'blobs'/sha(self.weight).replace(':','-'),self.store/'extra')
        with self.assertRaisesRegex(m.ServiceError,'hardlinked'):m.store_snapshot(self.rows)
    def resume_fixture(self):
        entry={'id':'test-fixture','engine':'ollama','reference':'fixture:exact','source':self.rows[0]['source'],'license':'Apache-2.0','license_url':'https://example.org/LICENSE','version':'exact','required_bytes':100,'digest':self.md,'user_setup_required':False}
        record=dict(entry,status='installed',size_bytes=100)
        prior=[{'stage':'model_installed','model':'test-fixture','record':record},{'stage':'acceptance_failed','error':'ServiceError: unexpected model store entry'},{'stage':'production_restored'},{'stage':'scheduler_restored'}]
        scope={'engine':fixed_engine_identity(m.NAME_PROVIDER,str(self.provider),self.store),'model_store':str(self.store),'generation_lock':str(m.HISTORICAL)}
        state={'pending':None,'scope':scope,'models':{'test-fixture':record}}
        return [entry],prior,state
    def test_complete_registry_resume_is_readonly_no_engine_or_install(self):
        catalog,prior,state=self.resume_fixture();manager=Mock();manager._read.return_value=state
        with patch.object(m,'read_private_json',return_value=prior),patch.object(m,'ModelManager',return_value=manager),patch.object(m,'digest',return_value='verified'),patch.object(m,'store_snapshot',return_value={'checked':True}):
            self.assertEqual(m.completed_download_resume(catalog,self.rows),({'checked':True},'verified'))
        manager.install.assert_not_called();manager.inspect.assert_not_called()
    def test_pending_journal_and_changed_scope_reject_resume(self):
        for change in ['pending','scope']:
            with self.subTest(change=change):
                catalog,prior,state=self.resume_fixture();state[change]={'uncertain':True};manager=Mock();manager._read.return_value=state
                with patch.object(m,'read_private_json',return_value=prior),patch.object(m,'ModelManager',return_value=manager):
                    with self.assertRaisesRegex(m.ServiceError,'registry'):m.completed_download_resume(catalog,self.rows)
                manager.install.assert_not_called()
    def test_prior_inference_or_missing_restore_reject_resume(self):
        for stage in ['job_submitted','runtime_ready','inference_completed']:
            catalog,prior,state=self.resume_fixture();prior.insert(0,{'stage':stage})
            with patch.object(m,'read_private_json',return_value=prior):
                with self.assertRaisesRegex(m.ServiceError,'runtime outcome'):m.completed_download_resume(catalog,self.rows)
if __name__=='__main__':unittest.main()
