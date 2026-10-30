import json
from pathlib import Path
import tempfile
import unittest
from inspect_trial_recovery import inspect_saved


class RecoveryTests(unittest.TestCase):
    def test_unknown_evidence_read_without_removal_or_restore(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);run_id='strata-20261030T000000Z-01234567';d=r/'backend-trials'/run_id;d.mkdir(parents=True)
            (r/'UNCERTAIN.json').write_text('{}')
            (d/'summary.json').write_text(json.dumps({'status':'UNKNOWN','generation_requests':1,'restoration':'UNKNOWN'}))
            result=inspect_saved(r,run_id)
            self.assertTrue(result['shared_unknown_present']);self.assertFalse(result['automatic_restore'])
            self.assertEqual(result['summary']['status'],'UNKNOWN');self.assertTrue((r/'UNCERTAIN.json').exists())
    def test_missing_summary_and_traversal_never_imply_cleanup_success(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);run_id='strata-20261030T000000Z-01234567';(r/'backend-trials'/run_id).mkdir(parents=True)
            result=inspect_saved(r,run_id)
            self.assertEqual(result['summary'],'MISSING_CONTROLLER_MAY_HAVE_DIED')
            self.assertIn('NOT_PROVEN',result['saved_owned_cleanup'])
            with self.assertRaises(ValueError):inspect_saved(r,'../anything')


if __name__=='__main__':unittest.main()
