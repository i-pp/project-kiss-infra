"""Human CPU-only static SGLang metadata/source probe. Never imports GPU packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parent
IMAGE='rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230'
COMMIT='baa9befa381511cd4d56f83980951e5a45fffc6d'
MANIFEST_SHA='a830fee756c7afb277e0fb313d3aadf9c408be21f20251955cade930d021f4c6'
PROBE_PREFIX='''import importlib.metadata as m,json,hashlib,re,sysconfig
from pathlib import Path
expected='''
PROBE_BODY='''
# -I -S suppresses site/.pth and image working-directory module imports.
roots=[Path('/opt/venv/lib/python3.12/site-packages'),Path('/usr/local/lib/python3.12/site-packages'),
       Path('/usr/lib/python3/dist-packages'),Path('/sgl-workspace/sglang/python'),Path('/sgl-workspace/aiter')]
roots += [Path(sysconfig.get_path(k)) for k in ['purelib','platlib']]
roots=list(dict.fromkeys(str(p) for p in roots if p.is_dir() and not p.is_symlink()))
normalize=lambda s:re.sub('[-_.]+','-',s).lower()
packages={}
for d in m.distributions(path=roots):
 name=d.metadata.get('Name','')
 if normalize(name) in {'torch','sglang','triton','pytorch-triton-rocm','compressed-tensors','transformers','safetensors','aiter','amd-aiter'}:
  packages[normalize(name)]={'version':d.version}
  if normalize(name)=='sglang':
   try:
    direct=json.loads(d.read_text('direct_url.json') or '{}');vcs=direct.get('vcs_info') or {};commit=vcs.get('commit_id')
    packages[normalize(name)]['reported_commit']=commit if isinstance(commit,str) and re.fullmatch('[0-9a-f]{40}',commit) else None
    packages[normalize(name)]['public_fixed_repo']=direct.get('url') in ['https://github.com/sgl-project/sglang','https://github.com/sgl-project/sglang.git']
   except (ValueError,TypeError):packages[normalize(name)]['provenance_parse_error']=True
out={'operation':'CPU_STATIC_METADATA_AND_SELECTED_SOURCE_HASH','packages':packages,'source_files':[],
     'generation_requests':0,'gpu_package_imports':False,'not_whole_source_attestation':True,'not_target_inference':True}
# The official recipe is an editable checkout. Read only fixed local locations.
source_roots=[Path('/sgl-workspace/sglang/python')]+[Path(p) for p in roots if 'site-packages' in p or 'dist-packages' in p]
for row in expected['files']:
 result={'path':row['path'],'expected_sha256':row['sha256'],'expected_bytes':row['bytes'],'matches':False}
 candidates=[]
 for base in source_roots:
  p=base/row['path']
  if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(base.resolve()) and p.stat().st_size<=2*1024*1024:
   raw=p.read_bytes();candidates.append({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 if candidates:
  result['candidates']=candidates
  result['matches']=all(c['bytes']==row['bytes'] and c['sha256']==row['sha256'] for c in candidates)
 else:result['missing']=True
 out['source_files'].append(result)
out['all_selected_source_files_match']=bool(out['source_files']) and all(x['matches'] for x in out['source_files'])
# Metadata/code-file equality is deliberately not an all-runtime or whole-commit claim.
print(json.dumps(out))
'''


def manifest():
    raw=(ROOT/'source_probe_manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('PINNED_MANIFEST_CHANGED')
    d=json.loads(raw)
    if d.get('source_commit')!=COMMIT or len(d.get('files',[]))!=4:raise ValueError('FIXED_FOUR_FILES_REQUIRED')
    for row in d['files']:
        if not row['path'].startswith('sglang/') or '..' in Path(row['path']).parts or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('UNSAFE_SOURCE_PATH')
    return d


def probe_text():return PROBE_PREFIX+repr(manifest())+'\n'+PROBE_BODY


def commands(uid,gid,token):
    if type(uid)is not int or uid<=0 or type(gid)is not int or gid<0 or not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('NONROOT_OWNED_IDENTITY_REQUIRED')
    name='aceis-sglang-content-'+token
    common=['/usr/bin/docker','--host','unix:///var/run/docker.sock']
    return [common+['image','inspect',IMAGE],common+['run','--pull=never','--rm','--no-healthcheck','--name',name,
            '--label','org.aceis.purpose=cpu-static-sglang-content','--label','org.aceis.owner='+str(uid),
            '--network','none','--ipc','private','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges:true','--user',str(uid)+':'+str(gid),
            '--cpus','1','--memory','256m','--memory-swap','256m','--pids-limit','64',
            '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m','--entrypoint','python3','-i',IMAGE,'-I','-S','-B','-']]


def verify_image(d):
    if not isinstance(d,list) or len(d)!=1:raise ValueError('IMAGE_SCHEMA')
    row=d[0]
    if IMAGE not in row.get('RepoDigests',[]) or row.get('Architecture')!='amd64' or row.get('Os')!='linux' or not re.fullmatch('sha256:[0-9a-f]{64}',row.get('Id','')):raise ValueError('FIXED_IMAGE_IDENTITY_MISMATCH')
    config=row.get('Config') or {}
    if config.get('Volumes'):raise ValueError('ANONYMOUS_VOLUME_DECLARATION_REJECTED')
    return {'image_ref':IMAGE,'image_id':row['Id'],'size_bytes':row.get('Size'),'labels':config.get('Labels') or {}}


def validate_probe_result(data):
    if (not isinstance(data,dict) or data.get('generation_requests')!=0
            or data.get('not_whole_source_attestation')is not True
            or data.get('gpu_package_imports')is not False):raise ValueError('CPU_RESPONSE_SCHEMA')
    expected=manifest()['files'];rows=data.get('source_files')
    if not isinstance(rows,list) or len(rows)!=len(expected):raise ValueError('CPU_SOURCE_RESPONSE_COUNT')
    matches=[]
    for want,row in zip(expected,rows):
        if (not isinstance(row,dict) or row.get('path')!=want['path']
                or row.get('expected_sha256')!=want['sha256'] or row.get('expected_bytes')!=want['bytes']):
            raise ValueError('CPU_SOURCE_RESPONSE_IDENTITY')
        candidates=row.get('candidates',[])
        if not isinstance(candidates,list):raise ValueError('CPU_SOURCE_CANDIDATES_SCHEMA')
        actual=bool(candidates) and all(isinstance(c,dict) and c.get('bytes')==want['bytes'] and c.get('sha256')==want['sha256'] for c in candidates)
        if row.get('matches')is not actual:raise ValueError('CPU_SOURCE_RESPONSE_FALSE_MATCH')
        matches.append(actual)
    if data.get('all_selected_source_files_match')is not all(matches):raise ValueError('CPU_SOURCE_SUMMARY_MISMATCH')
    if not isinstance(data.get('packages'),dict):raise ValueError('CPU_PACKAGE_RESPONSE_SCHEMA')
    return data


def invoke(argv,payload,timeout,guard):
    guard();proc=None
    try:
        proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        stdout,stderr=proc.communicate(input=payload.encode() if payload is not None else None,timeout=timeout)
    except BaseException:
        reaped=False
        if proc is not None:
            try:proc.kill()
            except BaseException:pass
            try:proc.wait(timeout=5);reaped=True
            except BaseException:pass
        raise RuntimeError('CLI_OUTCOME_UNKNOWN_REAP_'+str(reaped))
    finally:
        if proc is not None:
            for f in [proc.stdin,proc.stdout,proc.stderr]:
                if f is not None:f.close()
    if len(stdout)>2*1024*1024 or len(stderr)>2*1024*1024:raise RuntimeError('CPU_PROBE_OUTPUT_LIMIT')
    return proc.returncode,stdout.decode(),stderr.decode()


def installed_guard():
    if ROOT.parent.name!='backend-evaluation' or ROOT!=ROOT.parents[2]/'inference/backend-evaluation/sglang_content_handoff':raise ValueError('FIXED_INSTALLED_LAYOUT_REQUIRED')
    helper=ROOT.parent/'host_trial'
    if helper.is_symlink() or not (helper/'host_strata_trial.py').is_file():raise ValueError('FIXED_GUARD_MISSING')
    sys.path.insert(0,str(helper))
    from host_strata_trial import host_guard,private_dir,private_write
    repo=ROOT.parents[2];sys.path.insert(0,str(repo/'agents/local_llm'))
    from endpoint_config import private_json
    profile=private_json(repo/'agents/local_llm/.runtime/router-host-profile.json')
    def guard():
        if not sys.stdin.isatty() or os.getuid()==0:raise ValueError('NONROOT_HUMAN_TTY_REQUIRED')
        return host_guard(profile['orchestrator_root'])
    return repo,guard,private_dir,private_write


def terminate(signum,frame):raise KeyboardInterrupt('TERMINATED')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inspect-human',action='store_true');a=p.parse_args()
    if not a.inspect_human:
        print(json.dumps({'status':'PREPARED_HUMAN_CPU_INSPECTION_REQUIRED','image':IMAGE,'container_runs':0,'generation_requests':0}));return 0
    signal.signal(signal.SIGTERM,terminate)
    repo,guard,private_dir,write=installed_guard();guard();os.umask(0o077)
    root=private_dir(repo/'agents/local_llm/.runtime/backend-runtime/sglang-content-inspection'/('run-'+uuid.uuid4().hex))
    token=uuid.uuid4().hex;cmd=commands(os.getuid(),os.getgid(),token);name='aceis-sglang-content-'+token
    report={'status':'STARTING','owned_container_name':name,'container_run_intents':0,'generation_requests':0,'automatic_retry':False}
    try:
        code,out,_=invoke(cmd[0],None,15,guard)
        if code:raise ValueError('DOCKER_READ_UNAVAILABLE_NO_PRIVILEGE_RETRY')
        report['identity']=verify_image(json.loads(out))
        write(root/'intent.json',{'owned_container_name':name,'image_ref':IMAGE,'purpose':'ONE_CPU_STATIC_INSPECTION_NO_GPU'})
        report['container_run_intents']=1
        code,out,_=invoke(cmd[1],probe_text(),30,guard)
        if code:raise RuntimeError('CPU_PROBE_FAILED_NO_RETRY')
        data=validate_probe_result(json.loads(out))
        report['result']=data
        report['status']='SELECTED_SOURCE_MATCHED_NOT_RUNTIME_PASS' if data.get('all_selected_source_files_match')is True else 'SOURCE_DIFFERENCE_REQUIRES_REVIEW'
        print(json.dumps({**report,'receipt':str(root/'receipt.json')},indent=2))
        return 0 if data.get('all_selected_source_files_match')is True else 1
    except BaseException as exc:
        report.update(status='UNKNOWN_CPU_INSPECTION_NO_RETRY' if report['container_run_intents'] else 'BLOCKED_BEFORE_CPU_RUN',
                      reason=type(exc).__name__,instruction='Inspect the exact owned CPU-only container before any retry; CLI reap does not prove container exit.')
        print(json.dumps({**report,'receipt':str(root/'receipt.json')}));return 1
    finally:write(root/'receipt.json',report)


if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:
        print(json.dumps({'status':'BLOCKED','reason':type(exc).__name__,'automatic_retry':False}),file=sys.stderr);raise SystemExit(1)
