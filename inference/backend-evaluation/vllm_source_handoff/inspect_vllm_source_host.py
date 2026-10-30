"""Fixed existing-image CPU source attestation only. Never imports vLLM or GPU packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

IMAGE='vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905'
DOCKER='/usr/bin/docker'
ROOT=Path(__file__).resolve().parent
MANIFEST_SHA='8954472659b90206ec5963212254dbfc3f4c717ff9c735246db5b734e382aba2'
PROBE_PREFIX='''import importlib.metadata as m,json,hashlib,re
from pathlib import Path
expected='''
PROBE_BODY='''
out={'operation':'CPU_STATIC_SOURCE_HASH_NO_VLLM_IMPORT','packages':{},'source_files':[]}
for name in ['vllm','torch','transformers','triton','compressed-tensors','safetensors']:
 try:out['packages'][name]=m.version(name)
 except m.PackageNotFoundError:out['packages'][name]=None
d=m.distribution('vllm')
out['native_extension_files']=[str(x) for x in (d.files or []) if str(x).startswith('vllm/') and str(x).endswith('.so')][:50]
try:
 direct=json.loads(d.read_text('direct_url.json') or '{}');info=direct.get('vcs_info') or {}
 commit=info.get('commit_id')
 out['direct_url']={'public_fixed_repo':direct.get('url') in ['https://github.com/vllm-project/vllm','https://github.com/vllm-project/vllm.git'],
                    'commit_id':commit if isinstance(commit,str) and re.fullmatch('[0-9a-f]{40}',commit) else None}
except (ValueError,TypeError):out['direct_url']={'parse_error':True}
base=Path(d.locate_file('')).resolve()
for item in expected['files']:
 p=Path(d.locate_file(item['path']))
 row={'path':item['path'],'expected_sha256':item['sha256'],'expected_bytes':item['bytes']}
 if p.is_file() and p.resolve().is_relative_to(base) and p.stat().st_size<=2*1024*1024:
  raw=p.read_bytes();row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  row['matches']=len(raw)==item['bytes'] and row['sha256']==item['sha256']
 else:row.update(matches=False,missing_or_outside_distribution=True)
 out['source_files'].append(row)
out['all_critical_source_files_match']=all(x['matches'] for x in out['source_files'])
out['reported_commit_matches']=out.get('direct_url',{}).get('public_fixed_repo') is True and out['direct_url'].get('commit_id')==expected['source_commit']
out['not_whole_source_attestation']=True
out['not_target_inference']=True
out['generation_requests']=0
print(json.dumps(out))
'''


def manifest():
    raw=(ROOT/'source_probe_manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Pinned source probe manifest changed')
    d=json.loads(raw)
    if d.get('source_commit')!='5df63a7203cdb9328d824a27b682e77c7b9928be' or len(d.get('files',[]))!=7:
        raise ValueError('Fixed source manifest required')
    for row in d['files']:
        if (not row['path'].startswith('vllm/') or '..' in Path(row['path']).parts
                or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
            raise ValueError('Unsafe source manifest')
    return d


def probe_text():return PROBE_PREFIX+repr(manifest())+'\n'+PROBE_BODY


def commands(uid,gid,token):
    if not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('Unique owned name token required')
    name='aceis-vllm-source-'+token
    common=[DOCKER,'--host','unix:///var/run/docker.sock']
    return [common+['image','inspect',IMAGE],common+['run','--pull=never','--rm','--name',name,
        '--label','org.aceis.purpose=cpu-static-vllm-source','--network','none','--read-only',
        '--cap-drop','ALL','--security-opt','no-new-privileges:true','--user',str(uid)+':'+str(gid),
        '--cpus','1','--memory','256m','--memory-swap','256m','--pids-limit','64',
        '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m','--entrypoint','python3','-i',IMAGE,'-B','-']]


def verify_image(data):
    if (not isinstance(data,list) or len(data)!=1 or IMAGE not in data[0].get('RepoDigests',[])
            or data[0].get('Architecture')!='amd64' or data[0].get('Os')!='linux'
            or not re.fullmatch('sha256:[0-9a-f]{64}',data[0].get('Id',''))):
        raise ValueError('Fixed image identity mismatch')
    labels=data[0].get('Config',{}).get('Labels') or {}
    revisions={k:v for k,v in labels.items() if k in {'org.opencontainers.image.revision','org.label-schema.vcs-ref','vllm.commit','vllm_source_commit'} and isinstance(v,str) and re.fullmatch('[0-9a-f]{40}',v)}
    return {'image_ref':IMAGE,'image_id':data[0]['Id'],'size':data[0].get('Size'),'reported_revision_labels':revisions}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inspect-human',action='store_true');a=p.parse_args()
    if not a.inspect_human:
        print(json.dumps({'status':'PREPARED_HUMAN_CPU_INSPECTION_REQUIRED','docker_operations':0,'generation_requests':0}));return 0
    if ROOT.parent.name!='backend-evaluation':raise ValueError('Install beside fixed host_trial before live operation')
    sys.path.insert(0,str(ROOT.parent/'host_trial'))
    from host_strata_trial import host_guard
    repo=ROOT.parents[2];sys.path.insert(0,str(repo/'agents/local_llm'))
    from endpoint_config import private_json
    profile=private_json(repo/'agents/local_llm/.runtime/router-host-profile.json');host_guard(profile['orchestrator_root'])
    cmds=commands(os.getuid(),os.getgid(),uuid.uuid4().hex)
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    first=subprocess.run(cmds[0],capture_output=True,text=True,timeout=15,env=env)
    if first.returncode:
        print(json.dumps({'status':'BLOCKED_FIXED_IMAGE_OR_DOCKER_READ_UNAVAILABLE','no_privilege_retry':True}));return 1
    identity=verify_image(json.loads(first.stdout))
    try:result=subprocess.run(cmds[1],input=probe_text(),capture_output=True,text=True,timeout=30,env=env)
    except (subprocess.TimeoutExpired,KeyboardInterrupt):
        print(json.dumps({'status':'UNKNOWN_CPU_SOURCE_PROBE','owned_container_name':cmds[1][cmds[1].index('--name')+1],
            'automatic_retry':False,'instruction':'Inspect this owned CPU-only container before any repeat.'}));return 1
    if result.returncode or len(result.stdout)>2*1024*1024:
        print(json.dumps({'status':'UNKNOWN_OR_FAILED_CPU_SOURCE_PROBE','exit_code':result.returncode,'automatic_retry':False,
            'owned_container_name':cmds[1][cmds[1].index('--name')+1],'instruction':'Inspect owned CPU-only container state before repeating.'}));return 1
    data=json.loads(result.stdout);data.update(identity)
    data['status']='CRITICAL_SOURCE_MATCHED_NOT_TARGET_INFERENCE' if data.get('all_critical_source_files_match') else 'SOURCE_DIFFERENCE_REQUIRES_REVIEW'
    print(json.dumps(data,indent=2));return 0 if data.get('all_critical_source_files_match') else 1


if __name__=='__main__':raise SystemExit(main())
