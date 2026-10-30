import io
from pathlib import Path
import tempfile
import tarfile
import unittest
from acquire_strata_host import allowed,fetch,unpack


class AcquisitionTests(unittest.TestCase):
    def test_origin_and_redirect_destination_allowlist(self):
        self.assertEqual(allowed('https://github.com/a'), 'https://github.com/a')
        for u in ['http://github.com/a','https://evil.invalid/a','https://user:pw@github.com/a','file:///etc/passwd']:
            with self.assertRaises(ValueError):allowed(u)
    def test_size_digest_and_fresh_target_checked_without_network(self):
        class Opener:
            def open(self,*a,**k):return io.BytesIO(b'fixture')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'artifact'
            with self.assertRaises(ValueError):fetch('https://github.com/a',p,2,opener=Opener())
            with self.assertRaises(ValueError):fetch('https://github.com/a',p,20,opener=Opener())
            p.unlink()
            with self.assertRaises(ValueError):fetch('https://github.com/a',p,20,expected_sha='0'*64,opener=Opener())
    def test_tar_traversal_and_expanded_limit_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);f=root/'bad.tar.gz'
            with tarfile.open(f,'w:gz') as out:
                m=tarfile.TarInfo('../escape');m.size=1;out.addfile(m,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):unpack(f,root/'out',100)
            self.assertFalse((root/'escape').exists())
            f2=root/'large.tar.gz'
            with tarfile.open(f2,'w:gz') as out:
                m=tarfile.TarInfo('top/a');m.size=10;out.addfile(m,io.BytesIO(b'x'*10))
            with self.assertRaises(ValueError):unpack(f2,root/'out2',5,True)
    def test_source_root_strip_and_no_existing_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);f=root/'source.tar.gz'
            with tarfile.open(f,'w:gz') as out:
                m=tarfile.TarInfo('pinned/a.py');m.size=5;out.addfile(m,io.BytesIO(b'pass\n'))
            unpack(f,root/'out',100,True)
            self.assertEqual((root/'out/a.py').read_bytes(),b'pass\n')
            with self.assertRaises(ValueError):unpack(f,root/'out',100,True)


if __name__=='__main__':unittest.main()
