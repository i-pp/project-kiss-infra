import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from verified_assets_cache import verify, unchanged


class CacheTests(unittest.TestCase):
    def setUp(self):
        old_mask=os.umask(0o077);self.addCleanup(os.umask,old_mask)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.model=self.root/'model';self.model.mkdir()
        (self.model/'weights').write_bytes(b'original weights')
        self.cache=self.root/'cache'
        self.spec={'repo':'test/model','revision':'commit1','required_files':[{'name':'weights','bytes':16,'sha256':hashlib.sha256(b'original weights').hexdigest()}]}
    def run_verify(self,**kwargs):return verify(self.model,self.spec,self.cache,rate=None,**kwargs)
    def test_cold_then_hit_reads_no_model_content(self):
        a=self.run_verify();b=self.run_verify()
        self.assertEqual(a['mode'],'FULL_SHA256');self.assertEqual(a['bytes_hashed'],16)
        self.assertEqual(b['mode'],'METADATA_CACHE_HIT');self.assertEqual(b['bytes_hashed'],0)
        self.assertTrue(unchanged(b));self.assertFalse(list(self.cache.glob('.tmp-*')))
    def test_changed_same_size_and_restored_mtime_fails(self):
        a=self.run_verify();p=self.model/'weights';s=p.stat();p.write_bytes(b'corrupt! weights');os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns))
        self.assertFalse(unchanged(a))
        with self.assertRaisesRegex(ValueError,'SHA256'):self.run_verify()
    def test_missing_fails(self):
        self.run_verify();(self.model/'weights').unlink()
        with self.assertRaises(FileNotFoundError):self.run_verify()
    def test_replaced_identical_content_requires_full_hash(self):
        self.run_verify();p=self.model/'weights';p.rename(self.root/'old');p.write_bytes(b'original weights')
        self.assertEqual(self.run_verify()['mode'],'FULL_SHA256')
    def test_invalid_evidence_forces_full(self):
        self.run_verify();receipt=next(p for p in self.cache.glob('*.json'));receipt.write_text('[]')
        self.assertEqual(self.run_verify()['mode'],'FULL_SHA256')
    def test_manifest_revision_isolated(self):
        self.run_verify();self.spec['revision']='commit2'
        self.assertEqual(self.run_verify()['mode'],'FULL_SHA256')
    def test_oversized_evidence_not_a_hit(self):
        self.run_verify();receipt=next(p for p in self.cache.glob('*.json'))
        with receipt.open('a') as f:f.write(' '*(1<<20))
        self.assertEqual(self.run_verify()['mode'],'FULL_SHA256')
    def test_concurrent_mutation_before_commit_rejected(self):
        def mutate():(self.model/'weights').write_bytes(b'corrupt! weights')
        with self.assertRaisesRegex(ValueError,'changed'):self.run_verify(after_hash=mutate)
        self.assertFalse(list(self.cache.glob('*.json')))
    def test_change_after_return_detected(self):
        a=self.run_verify();(self.model/'weights').write_bytes(b'corrupt! weights')
        self.assertFalse(unchanged(a))
    def test_symlink_model_file_rejected(self):
        p=self.model/'weights';p.rename(self.root/'original');p.symlink_to(self.root/'original')
        with self.assertRaises(OSError):self.run_verify()
    def test_symlink_ancestor_rejected(self):
        self.model.rename(self.root/'real');self.model.symlink_to(self.root/'real')
        with self.assertRaises(OSError):self.run_verify()
    def test_new_unreviewed_file_rejected(self):
        self.run_verify();(self.model/'extra').touch()
        with self.assertRaisesRegex(ValueError,'Unexpected'):self.run_verify()
    def test_force_full(self):
        self.run_verify();self.assertEqual(self.run_verify(force=True)['bytes_hashed'],16)
    def test_concurrent_cache_writer_fails_nonblocking(self):
        self.run_verify()
        with (self.cache/'verification.lock').open('r+') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.run_verify()
    def test_manifest_hash_change_not_reused(self):
        self.run_verify();self.spec['required_files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA256'):self.run_verify()
    def test_untrusted_writable_model_rejected(self):
        (self.model/'weights').chmod(0o666)
        with self.assertRaisesRegex(ValueError,'permissions'):self.run_verify()


if __name__=='__main__':unittest.main()
