"""Native offline contracts. No live inference, process management or namespaces."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import model_selection as selection
import selection_extension as extension
from local_llm import LocalError

class SelectionTests(unittest.TestCase):
    def test_next_flash_and_120b_remain_distinct(self):
        rows={v['id']:v for v in selection.catalog()['profiles']}
        self.assertEqual(rows['qwen-coder-next']['quantization'],'Q4_K_M')
        self.assertEqual(rows['gpt-oss-120b']['gpu_layers'],20)
        self.assertFalse(rows['qwen38-flash-next']['selectable'])
        self.assertFalse(rows['qwen-coder-next']['route_configured'])
        self.assertIn('strict format FAIL',rows['qwen-coder-next']['historical_quality'])
    def test_unknown_identifier_never_constructs_a_client(self):
        factory=Mock(side_effect=AssertionError('No arbitrary route'))
        for identifier in ['http://example.test','/models/other.gguf','../qwen-coder-next',{},None]:
            with self.assertRaises(LocalError):selection.generate(identifier,'draft','x',client_factory=factory)
        factory.assert_not_called()
    def test_nonresident_selection_does_not_load_or_fallback(self):
        factory=Mock(side_effect=AssertionError('Must not contact 30B'))
        for identifier in ['gpt-oss-120b','qwen-coder-next']:
            with self.assertRaises(LocalError) as caught:
                selection.generate(identifier,'draft','x',client_factory=factory)
            self.assertEqual(caught.exception.code,'ROUTER_DEPLOYMENT_PENDING')
            status=selection.status(identifier,client_factory=factory)
            self.assertEqual(status['status'],'BLOCKED')
            self.assertFalse(status['executed'])
            self.assertEqual(status['quality_verdict'],'UNASSESSED')
        factory.assert_not_called()
    def test_resident_uses_original_client_without_new_options(self):
        client=Mock();client.generate.return_value={'model':'kiss-qwen3-coder-30b','verification_status':'NOT_EXECUTED'}
        factory=Mock(return_value=client)
        result=selection.generate('qwen-coder-30b','review','public fixture',17,client_factory=factory)
        client.generate.assert_called_once_with('review','public fixture',17)
        self.assertEqual(result['profile'],'qwen-coder-30b')
        self.assertEqual(result['verification_status'],'NOT_EXECUTED')
    def test_status_never_generates(self):
        client=Mock();client.status.return_value={'healthy':True};factory=Mock(return_value=client)
        result=selection.status('qwen-coder-30b',client_factory=factory)
        self.assertEqual(result['status'],'READY');client.generate.assert_not_called()
    def test_unavailable_resident_is_reported_without_fallback(self):
        client=Mock();client.status.side_effect=LocalError('MODEL_CHANGED','fixture')
        result=selection.status('qwen-coder-30b',client_factory=lambda:client)
        self.assertEqual(result['status'],'UNAVAILABLE');client.generate.assert_not_called()
    def test_flash_is_not_silently_treated_as_coder_next(self):
        factory=Mock()
        with self.assertRaises(LocalError) as caught:selection.generate('qwen38-flash-next','draft','x',client_factory=factory)
        self.assertEqual(caught.exception.code,'RESEARCH_ONLY');factory.assert_not_called()
    def test_asset_metadata_mismatch_is_not_reported_verified(self):
        with tempfile.TemporaryDirectory() as d, patch.object(selection,'ROOT',Path(d)):
            assets=selection.assets('qwen-coder-next')
            self.assertFalse(assets['present']);self.assertFalse(assets['current_full_sha256_recomputed'])
    def test_selected_tool_rejects_extra_authority_and_bounds(self):
        factory=Mock(side_effect=AssertionError('Must not create client'))
        for extra in [{'endpoint':'http://other'},{'command':'x'},{'model_path':'/x'},{'max_tokens':True},{'max_tokens':1025},{'prompt':'あ'*6000}]:
            args={'profile':'qwen-coder-30b','task':'draft','prompt':'fixture',**extra}
            result=extension.dispatch(extension.GENERATE,args,client_factory=factory)
            self.assertTrue(result['isError'])
        factory.assert_not_called()
    def test_blocked_tool_response_preserves_unexecuted_state(self):
        factory=Mock(side_effect=AssertionError('No backend'))
        result=extension.dispatch(extension.GENERATE,{'profile':'gpt-oss-120b','task':'review','prompt':'fixture'},client_factory=factory)
        self.assertTrue(result['isError']);self.assertFalse(result['structuredContent']['executed'])
        self.assertEqual(result['structuredContent']['error'],'ROUTER_DEPLOYMENT_PENDING')
        factory.assert_not_called()
    def test_unregistered_schema_exposes_no_lifecycle_or_arbitrary_destination(self):
        schemas=extension.definitions()
        self.assertEqual(len(schemas),3)
        self.assertTrue(schemas[0]['annotations']['readOnlyHint'])
        self.assertFalse(schemas[1]['annotations']['idempotentHint'])
        self.assertEqual(set(schemas[1]['inputSchema']['properties']),{'profile','task','prompt','max_tokens'})
        self.assertNotIn('qwen38-flash-next',schemas[1]['inputSchema']['properties']['profile']['enum'])
    def test_cli_nonresident_returns_blocked_without_generation(self):
        process=subprocess.run([sys.executable,'-B',str(Path(selection.__file__)),'generate','--profile','qwen-coder-next','--task','draft','--prompt','fixture'],capture_output=True,text=True,timeout=3)
        self.assertEqual(process.returncode,1)
        result=json.loads(process.stdout)
        self.assertEqual(result['error'],'ROUTER_DEPLOYMENT_PENDING');self.assertFalse(result['executed'])
    def test_resident_transport_uncertainty_is_never_called_not_started(self):
        client=Mock();client.generate.side_effect=LocalError('TRANSPORT_ERROR','fixture')
        result=extension.dispatch(extension.GENERATE,{'profile':'qwen-coder-30b','task':'draft','prompt':'fixture'},client_factory=lambda:client)
        self.assertTrue(result['isError'])
        self.assertEqual(result['structuredContent']['execution_status'],'UNKNOWN')
        self.assertIsNone(result['structuredContent']['executed'])
        self.assertFalse(result['structuredContent']['automatic_retry'])
        client.generate.assert_called_once()

    def test_registry_contains_no_executable_or_endpoint_configuration(self):
        value=json.loads(selection.REGISTRY_FILE.read_text())
        self.assertFalse(value['lifecycle_actions_enabled'])
        for row in value['profiles']:
            self.assertFalse(set(row)&{'command','endpoint','url','environment'})

if __name__=='__main__':unittest.main()
