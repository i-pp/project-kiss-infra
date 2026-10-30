import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('hostcheck',Path(__file__).with_name('host_deployment_check.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
SAFE={'available_bytes':40*module.GIB,'gpu_used_bytes':21*module.GIB,'swap_used_bytes':0}

class HostCheckTests(unittest.TestCase):
    def read(self,path):
        self.paths.append(path)
        if path=='/health':return {'status':'ok'}
        if path=='/models':return {'data':[{'id':alias,'status':{'value':'loaded' if alias==module.RESIDENT else 'unloaded'}} for alias in module.EXPECTED]}
        if path.startswith('/props'):return {'model_alias':module.RESIDENT,'default_generation_settings':{'n_ctx':32768},'total_slots':1}
        if path.startswith('/slots'):return [{'is_processing':False}]
        raise AssertionError('Unexpected path')
    def setUp(self):self.paths=[]
    def test_preflight_reads_no_model_management_path(self):
        result=module.check('preflight',self.read,lambda:SAFE)
        self.assertEqual(self.paths,['/health','/props','/slots'])
        self.assertEqual(result['generation_requests'],0)
    def test_router_gate_requires_exact_loaded_model_and_never_autoloads(self):
        module.check('router',self.read,lambda:SAFE)
        self.assertTrue(all('autoload=false' in p for p in self.paths if p.startswith(('/props','/slots'))))
        self.assertNotIn('/models/load',self.paths)
    def test_resource_pressure_prevents_all_http(self):
        with self.assertRaises(ValueError):module.check('preflight',self.read,lambda:{**SAFE,'available_bytes':23*module.GIB})
        self.assertEqual(self.paths,[])
    def test_unexpected_router_catalog_is_rejected(self):
        def read(path):
            if path=='/models':return {'data':[{'id':'unapproved','status':{'value':'loaded'}}]}
            return self.read(path)
        with self.assertRaises(ValueError):module.check('router',read,lambda:SAFE)
    def test_busy_slot_is_not_safe_to_stop(self):
        def read(path):return [{'is_processing':True}] if path.startswith('/slots') else self.read(path)
        with self.assertRaises(ValueError):module.check('preflight',read,lambda:SAFE)
    def test_wrong_resident_is_not_accepted_as_restore(self):
        def read(path):
            data=self.read(path)
            if path.startswith('/props'):data['model_alias']='other'
            return data
        with self.assertRaises(ValueError):module.check('resident',read,lambda:SAFE)
    def test_timeout_preserves_actual_endpoint_with_90_second_limit(self):
        now=[0.0]
        def sleep(seconds):now[0]+=seconds
        def read(path):
            now[0]=min(now[0]+2,90)
            raise module.ProbeError(path,'HTTP_TIMEOUT' if now[0]<90 else 'DEADLINE_EXPIRED')
        result=module.run_gate('router',read,lambda:SAFE,lambda:now[0],sleep)
        self.assertEqual(result['reason'],'HTTP_TIMEOUT');self.assertEqual(result['endpoint'],'/health')
        self.assertEqual(result['elapsed_seconds'],90)
        self.assertEqual(result['generation_requests'],0)
    def test_get_classifies_timeout_without_disclosing_response(self):
        with patch.object(module.http.client,'HTTPConnection') as connection:
            connection.return_value.getresponse.side_effect=TimeoutError('private exception text')
            with self.assertRaises(module.ProbeError) as caught:module.get('/health',module.time.monotonic()+2)
            self.assertEqual(caught.exception.code,'HTTP_TIMEOUT');self.assertEqual(caught.exception.path,'/health')
            self.assertNotIn('private',str(caught.exception))
            connection.return_value.close.assert_called_once()
    def test_private_gate_uses_only_get_to_verified_endpoint(self):
        from test_endpoint_config import fixture
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'llm/.runtime';fixture(root,candidate=True)
            target=module.endpoint_config.route(root,candidate=True)
            with patch.object(module.http.client,'HTTPConnection') as connection:
                connection.return_value.getresponse.return_value.status=200
                connection.return_value.getresponse.return_value.read.return_value=b'{"status":"ok"}'
                module.get('/health',module.time.monotonic()+2,target)
                self.assertEqual(connection.call_args.args,('172.19.0.2',8080))
                self.assertEqual(connection.return_value.request.call_args.args[:2],('GET','/health'))

if __name__=='__main__':unittest.main()
