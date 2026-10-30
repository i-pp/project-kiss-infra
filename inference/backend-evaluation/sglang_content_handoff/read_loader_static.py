"""Four fixed loader sources as AST data; no backend imports or source execution."""
import ast,hashlib,json,os,stat
from pathlib import Path
BASE='/sgl-workspace/sglang/python/sglang/srt/'
FILES=tuple(BASE+p for p in ['model_loader/loader.py','model_loader/weight_utils.py','configs/load_config.py','arg_groups/fields/model.py'])
SELECTED={'DefaultModelLoader.__init__','DefaultModelLoader._get_weights_iterator',
    '_validate_default_loader_extra_config','safetensors_weights_iterator',
    'buffered_multi_thread_safetensors_weights_iterator','LoadConfig.__post_init__'}


def inspect_file(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size>512*1024:raise ValueError('FIXED_SOURCE_SIZE_OR_TYPE')
        raw=f.read(512*1024+1)
    if len(raw)>512*1024:raise ValueError('FIXED_SOURCE_LIMIT')
    text=raw.decode();tree=ast.parse(text);functions={};fields={}
    for top in tree.body:
        children=[('',top)] if isinstance(top,ast.FunctionDef) else [(top.name+'.',n) for n in top.body] if isinstance(top,ast.ClassDef) else []
        for prefix,n in children:
            if isinstance(n,ast.FunctionDef) and prefix+n.name in SELECTED:functions[prefix+n.name]=ast.get_source_segment(text,n)
            if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='model_loader_extra_config':
                fields[prefix+n.target.id]=ast.get_source_segment(text,n)
    return {'status':'READ','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'functions_as_data':functions,'fields_as_data':fields,'source_executed':False}


def main():
    rows={}
    for p in FILES:
        try:rows[p]=inspect_file(p)
        except Exception as exc:rows[p]={'status':'UNAVAILABLE','error_class':type(exc).__name__}
    print(json.dumps({'status':'STATIC_SOURCE_ONLY_NO_BACKEND_IMPORT','files':rows,
        'source_executions':0,'gpu_operations':0,'generation_requests':0}))

if __name__=='__main__':main()
