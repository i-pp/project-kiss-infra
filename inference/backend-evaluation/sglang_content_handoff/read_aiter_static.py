"""Read fixed image source as data. Never import AITER/Torch or compile/run it."""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat

FILES=('/sgl-workspace/aiter/aiter/jit/core.py',
       '/sgl-workspace/aiter/aiter/jit/utils/cpp_extension.py',
       '/sgl-workspace/aiter/aiter/__init__.py',
       '/sgl-workspace/sglang/python/sglang/srt/layers/quantization/quark/schemes/quark_w4a4_mxfp4.py')
FUNCTIONS={'get_user_jit_dir','get_module_custom_op','get_module','build_module','_jit_compile'}
ASSIGNMENTS={'bd_dir','this_dir','__mds','AITER_ROOT_DIR','AITER_META_DIR'}


def inspect_file(path):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>512*1024:raise ValueError('FIXED_SOURCE_SIZE_OR_TYPE')
        raw=source.read(512*1024+1)
    if len(raw)>512*1024:raise ValueError('FIXED_SOURCE_LIMIT')
    text=raw.decode('utf-8');tree=ast.parse(text)
    functions={node.name:ast.get_source_segment(text,node) for node in tree.body
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in FUNCTIONS}
    assignments=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in ASSIGNMENTS for target in node.targets):
            assignments.append(ast.get_source_segment(text,node)[:2048])
    assignments=assignments[:32]
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'functions_as_data':functions,
        'module_assignments_as_data':assignments,
        'mentions_AITER_JIT_DIR':'AITER_JIT_DIR' in text,'source_executed':False}


def main():
    values={}
    for name in FILES:
        try:values[name]={'status':'READ',**inspect_file(name)}
        except Exception as exc:values[name]={'status':'UNAVAILABLE','error_class':type(exc).__name__}
    print(json.dumps({'status':'STATIC_SOURCE_ONLY_NO_BACKEND_IMPORT','files':values,
        'source_executions':0,'gpu_operations':0,'generation_requests':0}))


if __name__=='__main__':main()
