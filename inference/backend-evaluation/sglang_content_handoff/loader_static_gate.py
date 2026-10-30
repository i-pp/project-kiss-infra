"""Conservative structural compatibility check of captured source, never exec/import."""
import ast
from read_loader_static import BASE,FILES


def tree(source):
    if not isinstance(source,str) or len(source)>512*1024:raise ValueError('BOUNDED_SOURCE_TEXT_REQUIRED')
    return ast.parse(source)


def call_named(node,name):
    return any(isinstance(n,ast.Call) and (isinstance(n.func,ast.Name) and n.func.id==name
        or isinstance(n.func,ast.Attribute) and n.func.attr==name) for n in ast.walk(node))


def loader_flow(module):
    if len(module.body)!=1 or not isinstance(module.body[0],ast.FunctionDef):return False
    fn=module.body[0];parents={child:node for node in ast.walk(fn) for child in ast.iter_child_nodes(node)}
    direct=[n for n in fn.body if isinstance(n,ast.Assign) and len(n.targets)==1
            and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='use_multithread']
    if len(direct)!=1:return False
    initial=direct[0];v=initial.value
    if not (isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and v.func.attr=='get'
            and isinstance(v.func.value,ast.Name) and v.func.value.id=='extra_config'
            and len(v.args)==2 and isinstance(v.args[0],ast.Constant) and v.args[0].value=='enable_multithread_load'
            and isinstance(v.args[1],ast.Constant) and v.args[1].value is True):return False
    allowed_stores={id(initial.targets[0])}
    for n in ast.walk(fn):
        if n is not fn and isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):return False
        if isinstance(n,ast.Assign) and n is not initial and any(isinstance(t,ast.Name) and t.id=='use_multithread' for t in n.targets):
            if len(n.targets)!=1 or not isinstance(n.value,ast.Constant) or n.value.value is not False:return False
            allowed_stores.add(id(n.targets[0]))
    if any(isinstance(n,ast.Name) and n.id=='use_multithread' and isinstance(n.ctx,ast.Store) and id(n) not in allowed_stores for n in ast.walk(fn)):return False
    def assignment(body,name):
        return len(body)==1 and isinstance(body[0],ast.Assign) and len(body[0].targets)==1 and isinstance(body[0].targets[0],ast.Name) and body[0].targets[0].id=='weights_iterator' and isinstance(body[0].value,ast.Call) and isinstance(body[0].value.func,ast.Name) and body[0].value.func.id==name
    candidates=[n for n in ast.walk(fn) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='use_multithread'
                and assignment(n.body,'buffered_multi_thread_safetensors_weights_iterator') and assignment(n.orelse,'safetensors_weights_iterator')]
    if len(candidates)!=1:return False
    branch=candidates[0];node=branch
    while parents.get(node) is not fn:
        node=parents.get(node)
        if node is None:return False
        if isinstance(node,ast.If) and isinstance(node.test,ast.Constant):return False
        if isinstance(node,(ast.For,ast.While,ast.Try)):return False
    if any(isinstance(n,ast.Return) and n.lineno<branch.lineno for n in ast.walk(fn)):return False
    calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='buffered_multi_thread_safetensors_weights_iterator']
    return len(calls)==1 and calls[0] is branch.body[0].value


def confirm(data):
    files=data.get('files',{})
    if set(files)!=set(FILES) or any(v.get('status')!='READ' or v.get('source_executed') is not False for v in files.values()):
        raise ValueError('ALL_FIXED_LOADER_SOURCES_REQUIRED')
    def function(file,name):return tree(files[BASE+file]['functions_as_data'][name])
    loader=function('model_loader/loader.py','DefaultModelLoader._get_weights_iterator')
    branch=loader_flow(loader)
    keys=function('model_loader/loader.py','_validate_default_loader_extra_config')
    allowed=any(isinstance(n,ast.Set) and {'enable_multithread_load','num_threads'}<=set(x.value for x in n.elts if isinstance(x,ast.Constant)) for n in ast.walk(keys))
    serial=function('model_loader/weight_utils.py','safetensors_weights_iterator')
    mmap=call_named(serial,'safe_open') and not call_named(serial,'ThreadPoolExecutor')
    field=tree(files[BASE+'arg_groups/fields/model.py']['fields_as_data']['Model.model_loader_extra_config'])
    field_present=any(isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='model_loader_extra_config' for n in field.body)
    config=function('configs/load_config.py','LoadConfig.__post_init__')
    json_parse=call_named(config,'loads')
    if not all((branch,allowed,mmap,field_present,json_parse)):raise ValueError('SEQUENTIAL_LOADER_OPTION_NOT_CONFIRMED')
    return {'status':'STATIC_SEQUENTIAL_LOADER_BRANCH_CONFIRMED_NOT_RUNTIME_PASS',
        'enable_multithread_load':False,'num_threads':1,'source_executed':False,
        'source_sha256':{p:v['sha256'] for p,v in files.items()},
        'scope':'selected fields and branch only; other runtime/prefetch threads not globally limited'}
