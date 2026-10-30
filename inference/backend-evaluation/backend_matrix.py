"""Read-only backend inventory and finite handoff plans. No launch, POST or install."""
import argparse
import datetime
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import sys
import vllm_plan
from sglang_plan.sglang_prepare import evaluate as sglang_evaluate
from strata_plan.validate_plan import validate as strata_evaluate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]  # installed at <PROJECT_ROOT>/inference/backend-evaluation
PROFILES=('qwen-coder-next','qwen38-flash-next','gpt-oss-120b')
PORTS={'vllm':8081,'sglang':30000,'strata':8082}
LIMITS={'maximum_generations_per_feasible_configuration':1,'maximum_generation_retries':0,
        'initial_context':8192,'maximum_output_tokens':128,'temperature':0,'seed':42,
        'startup_seconds':90,'generation_seconds':90,'stop_seconds':45,
        'resident_restore_seconds':120,'whole_candidate_seconds':345,
        'ram_preflight_min_gib':24,'ram_running_min_gib':16,'gpu_max_gib':58,
        'parallel_gpu_inference':1,'nested_isolation':False,'unisolated_evaluator_fallback':False}


def inventory(root=ROOT):
    root=Path(root)
    nodes={}
    for name in ['/dev/kfd','/dev/dri/renderD128']:
        try:
            s=Path(name).stat();nodes[name]={'exists':True,'character_device':stat.S_ISCHR(s.st_mode)}
        except FileNotFoundError:nodes[name]={'exists':False}
    models={}
    registry=root/'agents/local_llm/model_registry.json'
    if registry.is_file():
        for p in json.loads(registry.read_text())['profiles']:
            if p['id'] not in PROFILES:continue
            directory=root/'models/large-coder-b3'/p['id'];files=[]
            for row in p['files']:
                name=row['name']
                if not isinstance(name,str) or Path(name).name!=name or name in ('','.','..'):raise ValueError('Unsafe fixed model filename')
                path=directory/name
                try:
                    s=path.lstat()
                    files.append({'name':name,'expected_bytes':row['bytes'],'observed_bytes':s.st_size,
                                  'regular':stat.S_ISREG(s.st_mode),'matches_size':s.st_size==row['bytes'] and stat.S_ISREG(s.st_mode)})
                except FileNotFoundError:files.append({'name':name,'matches_size':False,'missing':True})
            models[p['id']]={'format':p['quantization'],'files':files,'all_expected_assets_present':bool(files) and all(f['matches_size'] for f in files)}
    return {'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'device_scope':'This process execution namespace only; not physical host GPU absence or permission for another context',
            'gpu_nodes':nodes,'python_packages':{n:importlib.util.find_spec(n) is not None for n in ['torch','vllm','sglang']},
            'native_binaries':{n:shutil.which(n) for n in ['vllm','sglang','strata']},
            'assets':models,'free_disk_bytes':shutil.disk_usage(root).free,
            'generation_requests':0,'namespace_operations':0,'downloads':0}


def probe_api(backend,connection_factory=http.client.HTTPConnection):
    if backend not in PORTS:raise ValueError('Fixed backend required')
    result={'backend':backend,'host':'127.0.0.1','port':PORTS[backend],'reads':[],'generation_requests':0}
    for path in ['/health','/v1/models']:
        c=connection_factory('127.0.0.1',PORTS[backend],timeout=3)
        try:
            c.request('GET',path,headers={'Connection':'close'})
            response=c.getresponse();body=response.read(65537)
            row={'path':path,'http_status':response.status}
            if response.status==401:row['status']='AUTH_REQUIRED';result['reads'].append(row);break
            if 300<=response.status<400:row['status']='REDIRECT_REFUSED';result['reads'].append(row);break
            if response.status!=200 or len(body)>65536:row['status']='UNAVAILABLE';result['reads'].append(row);break
            data=json.loads(body) if body else {}
            if not isinstance(data,dict):raise ValueError('Expected object')
            if path=='/health':
                row['status']='HTTP_AVAILABLE'
                if type(data.get('loaded')) is bool:row['loaded']=data['loaded']
            else:
                rows=data.get('data',[])
                if not isinstance(rows,list):raise ValueError('Expected model list')
                row['model_ids']=[m.get('id') for m in rows if isinstance(m,dict) and isinstance(m.get('id'),str)][:8]
                row['status']='CATALOG_READ'
            result['reads'].append(row)
        except (OSError,ValueError,http.client.HTTPException) as e:
            result['reads'].append({'path':path,'status':'UNAVAILABLE','error_type':type(e).__name__});break
        finally:c.close()
    # Even successful GET is not version/model/weights/GPU execution proof.
    result['environment_verdict']='NOT_RUN';result['model_quality_verdict']='UNASSESSED'
    return result


def plans(observed):
    strata=json.loads((HERE/'strata_plan/strata-preparation.json').read_text())
    rows=[]
    for backend in PORTS:
        for profile in PROFILES:
            row=vllm_plan.evaluate(profile) if backend=='vllm' else sglang_evaluate(profile) if backend=='sglang' else strata_evaluate(strata,profile)
            blockers=list(row['blockers'])
            if not all(observed['gpu_nodes'].get(p,{}).get('exists') and observed['gpu_nodes'].get(p,{}).get('character_device')
                       for p in ['/dev/kfd','/dev/dri/renderD128']):
                blockers.append('NO_NATIVE_GPU_DEVICE_ACCESS_IN_CURRENT_CODEX_NAMESPACE')
            if not observed['assets'].get(profile,{}).get('all_expected_assets_present'):
                blockers.append('EXISTING_ASSET_IDENTITY_NOT_CONFIRMED')
            row.update(backend=backend,status='BLOCKED',blockers=list(dict.fromkeys(blockers)),generation_count=0,
                       environment_verdict='NOT_RUN',model_quality_verdict='UNASSESSED',limits=LIMITS,
                       gpu_scope_note='Missing native GPU nodes does not forbid calling an already authorized remote/local API; none is deployed by this tool.')
            rows.append(row)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observe-api',action='store_true',help='GET only the three fixed candidate loopback APIs; no autoload or retries')
    args=p.parse_args();observed=inventory()
    result={'inventory':observed,'candidates':plans(observed),'backend_launches':0,'generations':0,'docker_operations':0}
    if args.observe_api:result['api_reads']=[probe_api(b) for b in PORTS]
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
