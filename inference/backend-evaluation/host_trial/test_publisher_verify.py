import json
from pathlib import Path
import tempfile
import unittest
from publisher_verify import verify_payload,verify_signed_bundle,KEY_ID


class PublisherTests(unittest.TestCase):
    def test_real_public_release_feed_signature(self):
        root=Path(__file__).parent
        self.assertEqual(verify_payload((root/'publisher-feed.json').read_bytes(),json.loads((root/'publisher-feed.json.sig').read_text())),KEY_ID)
    def test_tampered_feed_and_unknown_signer_fail(self):
        root=Path(__file__).parent;payload=(root/'publisher-feed.json').read_bytes();sig=json.loads((root/'publisher-feed.json.sig').read_text())
        with self.assertRaises(ValueError):verify_payload(payload+b' ',sig)
        sig['key_id']='0'*16
        with self.assertRaises(ValueError):verify_payload(payload,sig)
    def test_unsigned_or_changed_bundle_never_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'engine-component.json').write_text('{"signature":null}')
            with self.assertRaises(ValueError):verify_signed_bundle(p)


if __name__=='__main__':unittest.main()
