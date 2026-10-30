import struct
import tempfile
from pathlib import Path
import unittest
from inspect_gguf_header import inspect,CAP


def s(text):
    raw=text.encode();return struct.pack('<Q',len(raw))+raw


class HeaderTests(unittest.TestCase):
    def test_architecture_without_reading_tensor_payload(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fixture.gguf'
            header=b'GGUF'+struct.pack('<IQQ',3,1,1)+s('general.architecture')+struct.pack('<I',8)+s('qwen3next')
            p.write_bytes(header+b'TENSOR_BYTES_ARE_NOT_PARSED')
            r=inspect(p)
            self.assertEqual(r['general.architecture'],'qwen3next');self.assertEqual(r['bytes_addressed_through'],len(header))
            self.assertFalse(r['tensor_bodies_read'])
    def test_truncated_and_unbounded_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fixture.gguf';p.write_bytes(b'GGUF')
            with self.assertRaises(ValueError):inspect(p)
            p.write_bytes(b'GGUF'+struct.pack('<IQQ',3,1,1)+struct.pack('<Q',CAP+1))
            with self.assertRaises(ValueError):inspect(p)


if __name__=='__main__':unittest.main()
