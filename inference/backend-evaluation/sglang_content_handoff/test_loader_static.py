import hashlib,tempfile,unittest
from pathlib import Path
import read_loader_static as r
import loader_static_gate as g


def fixture():
    snippets={
        'model_loader/loader.py':{
            'DefaultModelLoader._get_weights_iterator':'''def _get_weights_iterator(self):
    use_multithread = extra_config.get("enable_multithread_load", True)
    if use_multithread:
        weights_iterator = buffered_multi_thread_safetensors_weights_iterator(files)
    else:
        weights_iterator = safetensors_weights_iterator(files)
''',
            '_validate_default_loader_extra_config':'''def check():
    allowed_keys={"enable_multithread_load", "num_threads"}
'''},
        'model_loader/weight_utils.py':{'safetensors_weights_iterator':'''def serial(files):
    with safetensors.safe_open(files[0]) as f:
        yield f.get_tensor("a")
'''},
        'configs/load_config.py':{'LoadConfig.__post_init__':'''def parse(self):
    self.model_loader_extra_config=orjson.loads(value)
'''},
        'arg_groups/fields/model.py':{}}
    files={r.BASE+n:{'status':'READ','source_executed':False,'bytes':100,'sha256':'a'*64,'functions_as_data':v,'fields_as_data':{}} for n,v in snippets.items()}
    files[r.BASE+'arg_groups/fields/model.py']['fields_as_data']={'Model.model_loader_extra_config':'model_loader_extra_config: str = "{}"'}
    return {'files':files}


class StaticLoaderTests(unittest.TestCase):
    def test_positive_branch_and_fields_are_read_as_data(self):
        out=g.confirm(fixture());self.assertFalse(out['source_executed']);self.assertFalse(out['enable_multithread_load'])
    def test_missing_option_branch_json_parser_or_cpu_serial_path_blocks(self):
        for file,fn,value in [
            ('model_loader/loader.py','DefaultModelLoader._get_weights_iterator','def f():\n    pass'),
            ('model_loader/loader.py','_validate_default_loader_extra_config','def f():\n    allowed_keys={"other"}'),
            ('configs/load_config.py','LoadConfig.__post_init__','def f():\n    pass'),
            ('model_loader/weight_utils.py','safetensors_weights_iterator','def f():\n    return ThreadPoolExecutor()')]:
            data=fixture();data['files'][r.BASE+file]['functions_as_data'][fn]=value
            with self.assertRaises((ValueError,KeyError)):g.confirm(data)
    def test_forced_parallel_dead_branch_and_early_return_are_rejected(self):
        original=fixture()['files'][r.FILES[0]]['functions_as_data']['DefaultModelLoader._get_weights_iterator']
        cases=[original.replace('    if use_multithread:', '    use_multithread = True\n    if use_multithread:'),
               original.replace('    if use_multithread:', '    return None\n    if use_multithread:'),
               original.replace('    if use_multithread:', '    if False:\n        if use_multithread:').replace('        weights_iterator = buffered','            weights_iterator = buffered').replace('    else:', '        else:').replace('        weights_iterator = safetensors','            weights_iterator = safetensors')]
        for source in cases:
            data=fixture();data['files'][r.FILES[0]]['functions_as_data']['DefaultModelLoader._get_weights_iterator']=source
            with self.assertRaises(ValueError):g.confirm(data)
    def test_unavailable_file_and_execution_claim_are_rejected(self):
        for key,value in [('status','UNAVAILABLE'),('source_executed',True)]:
            data=fixture();data['files'][r.FILES[0]][key]=value
            with self.assertRaises(ValueError):g.confirm(data)
    def test_source_reader_never_executes_module_or_imports_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'fixture.py';p.write_text('raise AssertionError("must never execute")\nimport torch\nclass DefaultModelLoader:\n def _get_weights_iterator(self):\n  return 1\n')
            out=r.inspect_file(p);self.assertFalse(out['source_executed']);self.assertIn('DefaultModelLoader._get_weights_iterator',out['functions_as_data'])
            self.assertEqual(out['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
    def test_invalid_size_or_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source';p.write_bytes(b'x'*(512*1024+1))
            with self.assertRaises(ValueError):r.inspect_file(p)
            link=Path(temp)/'link';link.symlink_to(p)
            with self.assertRaises(OSError):r.inspect_file(link)

if __name__=='__main__':unittest.main()
