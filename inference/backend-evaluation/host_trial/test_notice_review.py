"""Fake documentation binding only; no third-party or engine execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from notice_review import verify
from publisher_verify import MANIFEST_SHA


class NoticeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.bundle=self.root/'bundle';self.bundle.mkdir()
        (self.bundle/'engine-component.json').write_text(json.dumps({'files':[{'path':'strata'},{'path':'libfixture.so'}]}))
        self.doc=self.root/'upstream-license.txt';self.doc.write_text('Fixture terms read; no execution here.')
        self.data={'schema':1,'bundle_manifest_sha256':MANIFEST_SHA,
            'scope':'ONE_INTERNAL_EVALUATION_NO_REDISTRIBUTION','documents_actually_read':True,
            'unresolved_local_execution':[],'unresolved_redistribution':['Exact source/build mapping not proven'],
            'covered_bundle_artifacts':['strata','libfixture.so'],
            'documents':[{'id':'official','origin_url':'https://example.org/fixed/LICENSE',
                'path':str(self.doc),'sha256':hashlib.sha256(self.doc.read_bytes()).hexdigest(),'actually_read':True}],
            'components':[{'artifacts':['strata','libfixture.so'],'document_ids':['official'],
                'local_execution_review':'REVIEWED','provenance_limitations':'Fixture build identity incomplete'}]}
        self.evidence=self.root/'review.json'
    def tearDown(self):self.tmp.cleanup()
    def reference(self):
        self.evidence.write_text(json.dumps(self.data));self.evidence.chmod(0o600)
        return {'path':str(self.evidence),'sha256':hashlib.sha256(self.evidence.read_bytes()).hexdigest()}
    def test_external_primary_documents_bind_without_mutating_bundle(self):
        result=verify(self.reference(),self.bundle)
        self.assertEqual(result['covered_artifacts'],2)
        self.assertEqual(result['unresolved_redistribution'],self.data['unresolved_redistribution'])
        self.assertFalse(result['legal_compliance_claimed'])
        self.assertEqual(sorted(p.name for p in self.bundle.iterdir()),['engine-component.json'])
    def test_changed_document_or_review_record_cannot_pass_cached_acknowledgment(self):
        reference=self.reference();self.doc.write_text('different')
        with self.assertRaises(ValueError):verify(reference,self.bundle)
        self.evidence.write_text('{}')
        with self.assertRaises(ValueError):verify(reference,self.bundle)
    def test_unread_documents_or_unresolved_local_terms_block(self):
        original=copy.deepcopy(self.data)
        for mutation in ['overall','document','local']:
            self.data=copy.deepcopy(original)
            if mutation=='overall':self.data['documents_actually_read']='true'
            if mutation=='document':self.data['documents'][0]['actually_read']=False
            if mutation=='local':self.data['unresolved_local_execution']=['Unknown EULA']
            with self.assertRaises(ValueError):verify(self.reference(),self.bundle)
    def test_bundle_scope_or_missing_coverage_blocks(self):
        original=copy.deepcopy(self.data)
        for mutation in ['bundle','scope','coverage','mapping']:
            self.data=copy.deepcopy(original)
            if mutation=='bundle':self.data['bundle_manifest_sha256']='0'*64
            if mutation=='scope':self.data['scope']='PUBLIC_DISTRIBUTION'
            if mutation=='coverage':self.data['covered_bundle_artifacts']=['strata']
            if mutation=='mapping':self.data['components'][0]['artifacts']=['strata']
            with self.assertRaises(ValueError):verify(self.reference(),self.bundle)
    def test_unsafe_or_symlinked_evidence_is_rejected(self):
        ref=self.reference();self.evidence.chmod(0o644)
        with self.assertRaises(ValueError):verify(ref,self.bundle)
        self.evidence.chmod(0o600);self.doc.unlink();self.doc.symlink_to(self.evidence)
        with self.assertRaises(ValueError):verify(ref,self.bundle)


if __name__=='__main__':unittest.main()
