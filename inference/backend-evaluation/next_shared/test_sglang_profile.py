"""Selected SGLang registry CPU tests only. No GPU, Docker, HTTP, or helpers."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
import fixed_trial_assets as a

ROOT=Path(__file__).resolve().parent

class SGLangProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)/'project';(self.project/'agents/local_llm').mkdir(parents=True)
        scope=patch.object(a,'FIXED_PROJECT_ROOT',self.project);scope.start();self.addCleanup(scope.stop)
        # Any accidental backend/helper import fails even in this CPU suite.
        helper=patch.object(a,'helpers',side_effect=AssertionError('no host helper/import'));helper.start();self.addCleanup(helper.stop)
        self.baseline=json.loads((ROOT/'vllm-ready.snapshot.json').read_text())
        self.sg=json.loads((ROOT/'sglang-runtime.snapshot.json').read_text())
    def record(self,backend='sglang'):
        d=copy.deepcopy(self.baseline);d['project_root']=str(self.project);d['model_dir']=str(self.project/a.MODEL_RELATIVE)
        d['review']['fixed_jit_cache_exec_reviewed']=True
        if backend=='sglang':
            d['runtimes']['sglang']=copy.deepcopy(self.sg)
            d['runtimes']['sglang']['source_dependency_match_reviewed']=True
            d['runtimes']['sglang']['bootstrap_complete_reviewed']=True
        return d
    def parse(self,d,backend='sglang',purpose='trial'):
        raw=(json.dumps(d,indent=2)+'\n').encode();p=Path(self.temp.name)/(uuid.uuid4().hex+'.json')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw)
        return a.operator_record(p,hashlib.sha256(raw).hexdigest(),backend=backend,purpose=purpose)
    def test_legacy_source_registry_unchanged(self):
        self.assertEqual(a.SOURCE,{'vllm':'5df63a7203cdb9328d824a27b682e77c7b9928be','sglang':'baa9befa381511cd4d56f83980951e5a45fffc6d'})
    def test_current_vllm_candidate_accepted_without_runtime_changes(self):
        d=self.record('vllm');r=self.parse(d,'vllm')
        self.assertEqual(r['runtimes'],self.baseline['runtimes'])
    def test_vllm_unused_old_sglang_pin_does_not_require_new_fields(self):
        d=self.record('vllm');d['runtimes']['sglang'].update(image_ref=None,image_id=None,source_dependency_match_reviewed=False,bootstrap_complete_reviewed=False)
        self.assertEqual(self.parse(d,'vllm')['runtimes']['sglang']['source_commit'],a.SOURCE['sglang'])
    def test_reviewed_selected_sglang_profile_can_pass_cpu_contract(self):
        d=self.record();self.assertEqual(self.parse(d)['runtimes']['sglang']['source_commit'],'ebfbd3ea35acf6e9facbe74e627d37c3542e5fc1')
    def test_pending_top_level_approval_is_rejected(self):
        d=self.record();d['review']={k:False for k in d['review']}
        with self.assertRaisesRegex(a.Blocked,'OPERATOR_REVIEW_MISSING'):self.parse(d)
    def test_pending_source_review_rejected(self):
        d=self.record();d['runtimes']['sglang']['source_dependency_match_reviewed']=False
        with self.assertRaisesRegex(a.Blocked,'REVIEW_PENDING'):self.parse(d)
    def test_pending_bootstrap_review_rejected(self):
        d=self.record();d['runtimes']['sglang']['bootstrap_complete_reviewed']=False
        with self.assertRaisesRegex(a.Blocked,'REVIEW_PENDING'):self.parse(d)
    def test_different_image_reference_rejected(self):
        d=self.record();d['runtimes']['sglang']['image_ref']='rocm/sgl-dev@sha256:'+'1'*64
        with self.assertRaises(a.Blocked):self.parse(d)
    def test_different_image_id_rejected(self):
        d=self.record();d['runtimes']['sglang']['image_id']='sha256:'+'2'*64
        with self.assertRaises(a.Blocked):self.parse(d)
    def test_legacy_or_arbitrary_selected_source_rejected(self):
        for commit in [a.SOURCE['sglang'],'0'*40]:
            with self.subTest(commit=commit):
                d=self.record();d['runtimes']['sglang']['source_commit']=commit
                with self.assertRaises(a.Blocked):self.parse(d)
    def test_each_dependency_version_is_exactly_bound(self):
        for name in self.sg['dependency_versions']:
            with self.subTest(package=name):
                d=self.record();d['runtimes']['sglang']['dependency_versions'][name]='0.0.1'
                with self.assertRaises(a.Blocked):self.parse(d)
        d=self.record();d['runtimes']['sglang']['dependency_versions']['unexpected']='1.0.0'
        with self.assertRaises(a.Blocked):self.parse(d)
    def test_evidence_digest_tamper_rejected(self):
        d=self.record();d['runtimes']['sglang']['source_evidence_sha256']='0'*64
        with self.assertRaises(a.Blocked):self.parse(d)
    def test_whole_commit_scope_upgrade_rejected(self):
        d=self.record();d['runtimes']['sglang']['source_equivalence_scope']='whole-commit'
        with self.assertRaises(a.Blocked):self.parse(d)
    def test_missing_scope_or_extra_profile_field_rejected(self):
        d=self.record();del d['runtimes']['sglang']['source_equivalence_scope']
        with self.assertRaisesRegex(a.Blocked,'SCHEMA'):self.parse(d)
        d=self.record();d['runtimes']['sglang']['arbitrary_url']='http://example.invalid'
        with self.assertRaisesRegex(a.Blocked,'SCHEMA'):self.parse(d)
    def test_old_trial_record_without_explicit_jit_ack_is_rejected(self):
        for backend in ['vllm','sglang']:
            for flag in [None,False,'true',1]:
                d=self.record(backend)
                if flag is None:del d['review']['fixed_jit_cache_exec_reviewed']
                else:d['review']['fixed_jit_cache_exec_reviewed']=flag
                with self.assertRaisesRegex(a.Blocked,'fixed_jit_cache_exec_reviewed'):self.parse(d,backend)
    def test_legacy_acquisition_does_not_require_trial_only_jit_ack(self):
        d=self.record('vllm');del d['review']['fixed_jit_cache_exec_reviewed']
        self.assertEqual(self.parse(d,'vllm',purpose='acquire')['model_dir'],d['model_dir'])
    def test_portable_fixture_and_reviewed_jit_profile_bytes(self):
        state=json.loads((ROOT/'staging-state.fixture.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'vllm-ready.snapshot.json').read_bytes()).hexdigest(),state['vllm_ready_sanitized_fixture_sha256'])
        jit=json.loads((ROOT/'jit-cache-state.fixture.json').read_text())
        self.assertEqual(jit['source_host_api_trial_sha256'],state['host_api_trial_unchanged_sha256'])
        self.assertEqual(hashlib.sha256((ROOT/'host_api_trial.py').read_bytes()).hexdigest(),jit['proposed_host_api_trial_sha256'])

if __name__=='__main__':unittest.main()
