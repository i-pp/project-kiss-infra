import tempfile
from pathlib import Path
import unittest
from read_aiter_static import inspect_file


class StaticReaderTests(unittest.TestCase):
    def test_source_is_read_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'core.py';p.write_text("raise RuntimeError('MUST_NOT_RUN')\nthis_dir='/image/pkg/jit'\nbd_dir=f'{get_user_jit_dir()}/build'\ndef get_user_jit_dir():\n    return 'AITER_JIT_DIR'\n")
            result=inspect_file(p);self.assertFalse(result['source_executed'])
            self.assertIn('get_user_jit_dir',result['functions_as_data']);self.assertTrue(result['mentions_AITER_JIT_DIR'])
            self.assertEqual(len(result['module_assignments_as_data']),2)
    def test_symlink_or_oversize_source_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'core.py';p.write_bytes(b'x'*(512*1024+1));link=Path(tmp)/'link';link.symlink_to(p)
            with self.assertRaises(OSError):inspect_file(link)
            with self.assertRaises(ValueError):inspect_file(p)


if __name__=='__main__':unittest.main()
