import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import backend_matrix as bm


class MatrixTests(unittest.TestCase):
    def observed(self):
        return {'gpu_nodes':{p:{'exists':True,'character_device':True} for p in ['/dev/kfd','/dev/dri/renderD128']},
                'assets':{p:{'all_expected_assets_present':True} for p in bm.PROFILES}}
    def test_nine_unverified_configurations_cannot_become_execution_pass(self):
        rows=bm.plans(self.observed())
        self.assertEqual(len(rows),9)
        self.assertTrue(all(r['status']=='BLOCKED' and r['generation_count']==0 and r['environment_verdict']=='NOT_RUN' for r in rows))
        for r in rows:
            if r['backend']=='sglang':self.assertIn('GGUF_HIP_UNSUPPORTED',r['blockers'])
            if r['backend']=='strata' and r['profile']!='qwen38-flash-next':self.assertIn('NO_VERIFIED_STRATA_ARCHITECTURE_PATH',r['blockers'])
    def test_missing_gpu_scope_does_not_claim_physical_gpu_absence(self):
        facts=self.observed();facts['gpu_nodes']={'kfd':{'exists':False}}
        for row in bm.plans(facts):
            self.assertIn('NO_NATIVE_GPU_DEVICE_ACCESS_IN_CURRENT_CODEX_NAMESPACE',row['blockers'])
            self.assertIn('already authorized',row['gpu_scope_note'])
    def test_actual_asset_inventory_uses_regular_files_and_expected_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'agents/local_llm';config.mkdir(parents=True)
            model=root/'models/large-coder-b3/qwen-coder-next';model.mkdir(parents=True)
            path=model/'fixture.gguf';path.write_bytes(b'GGUF')
            (config/'model_registry.json').write_text(json.dumps({'profiles':[{'id':'qwen-coder-next','quantization':'Q4_K_M','files':[{'name':'fixture.gguf','bytes':4}]}]}))
            self.assertTrue(bm.inventory(root)['assets']['qwen-coder-next']['all_expected_assets_present'])
            path.write_bytes(b'wrong-size')
            self.assertFalse(bm.inventory(root)['assets']['qwen-coder-next']['all_expected_assets_present'])
    def test_registry_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'agents/local_llm';config.mkdir(parents=True)
            (config/'model_registry.json').write_text(json.dumps({'profiles':[{'id':'qwen-coder-next','quantization':'Q4_K_M','files':[{'name':'../escape','bytes':4}]}]}))
            with self.assertRaises(ValueError):bm.inventory(root)


class ApiTests(unittest.TestCase):
    def factory(self,responses):
        factory=Mock();connections=[]
        for status,body in responses:
            response=Mock(status=status);response.read.return_value=body
            conn=Mock();conn.getresponse.return_value=response;connections.append(conn)
        factory.side_effect=connections
        return factory,connections
    def test_b1_empty_health_is_valid_without_assuming_target_inference(self):
        factory,connections=self.factory([(200,b''),(200,b'{"data":[{"id":"small-b1-model"}]}')])
        out=bm.probe_api('vllm',factory)
        self.assertEqual([r['status'] for r in out['reads']],['HTTP_AVAILABLE','CATALOG_READ'])
        self.assertEqual(out['environment_verdict'],'NOT_RUN')
        self.assertEqual(factory.call_args.args,('127.0.0.1',8081))
        self.assertTrue(all(c.request.call_args.args[0]=='GET' for c in connections))
    def test_strata_healthy_but_unloaded_is_not_runtime_pass(self):
        factory,_=self.factory([(200,b'{"loaded":false}'),(200,b'{"data":[]}')])
        out=bm.probe_api('strata',factory)
        self.assertFalse(out['reads'][0]['loaded']);self.assertEqual(out['model_quality_verdict'],'UNASSESSED')
        self.assertEqual(out['generation_requests'],0)
    def test_auth_and_redirect_stop_without_retry_or_credential(self):
        for status,verdict in [(401,'AUTH_REQUIRED'),(302,'REDIRECT_REFUSED')]:
            factory,connections=self.factory([(status,b'')])
            out=bm.probe_api('sglang',factory)
            self.assertEqual(out['reads'][0]['status'],verdict);self.assertEqual(factory.call_count,1)
            self.assertNotIn('Authorization',connections[0].request.call_args.kwargs['headers'])
            connections[0].close.assert_called_once()
    def test_timeout_is_single_attempt_not_generation_or_retry(self):
        factory,connections=self.factory([(200,b'')]);connections[0].getresponse.side_effect=TimeoutError()
        out=bm.probe_api('strata',factory)
        self.assertEqual(factory.call_count,1);self.assertEqual(out['reads'][0]['error_type'],'TimeoutError')
        self.assertEqual(out['generation_requests'],0)
    def test_response_size_and_json_are_bounded(self):
        for body in [b'x'*65537,b'[]',b'not-json']:
            factory,_=self.factory([(200,body)])
            out=bm.probe_api('vllm',factory)
            self.assertEqual(out['reads'][0]['status'],'UNAVAILABLE');self.assertEqual(factory.call_count,1)
    def test_arbitrary_backend_address_rejected_before_connect(self):
        factory=Mock()
        with self.assertRaises(ValueError):bm.probe_api('http://arbitrary.invalid',factory)
        factory.assert_not_called()


if __name__=='__main__':unittest.main()
