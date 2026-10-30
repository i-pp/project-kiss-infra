"""Human-host CPU-only metadata probe of the already-approved fixed B1 image."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from host_strata_trial import host_guard

IMAGE='vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905'
PROBE='''import importlib.metadata as m,json,sys
names=['vllm','vllm-gguf-plugin','torch','transformers','gguf','triton','compressed-tensors','safetensors','sglang']
out={'operation':'DISTRIBUTION_METADATA_ONLY_NO_GPU_IMPORT','python':sys.version,'packages':{}}
for name in names:
 try:
  d=m.distribution(name);r={'version':d.version,'entry_points':[{'name':e.name,'group':e.group,'value':e.value} for e in d.entry_points]}
  if name=='vllm-gguf-plugin':r['requires']=d.requires
  out['packages'][name]=r
 except m.PackageNotFoundError:out['packages'][name]={'installed':False}
print(json.dumps(out))
'''


def commands(uid,gid,token):
    if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Fixed token required')
    name='project-kiss-vllm-metadata-'+token
    return [['docker','image','inspect',IMAGE,'--format','{{json .RepoDigests}}'],
      ['docker','run','--pull','never','--rm','--name',name,'--label','io.aceis.purpose=cpu-only-vllm-metadata',
       '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
       '--user',str(uid)+':'+str(gid),'--cpus','1','--memory','256m','--memory-swap','256m',
       '--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m','--entrypoint','python3','-i',IMAGE,'-B','-']]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inspect-human',action='store_true');a=p.parse_args()
    if not a.inspect_human:
        print(json.dumps({'status':'PREPARED_HUMAN_HOST_CHECK_REQUIRED','image':IMAGE,'docker_operations':0}));return 0
    repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'agents/local_llm'))
    from endpoint_config import private_json
    profile=private_json(repo/'agents/local_llm/.runtime/router-host-profile.json')
    host_guard(profile['orchestrator_root'])
    cmds=commands(os.getuid(),os.getgid(),uuid.uuid4().hex)
    observed=subprocess.run(cmds[0],capture_output=True,text=True,timeout=15)
    if observed.returncode or IMAGE not in json.loads(observed.stdout):
        print(json.dumps({'status':'BLOCKED_FIXED_IMAGE_OR_DOCKER_READ_UNAVAILABLE','stderr':observed.stderr[:1000],'no_privilege_retry':True}));return 1
    try:
        r=subprocess.run(cmds[1],input=PROBE,capture_output=True,text=True,timeout=30)
    except subprocess.TimeoutExpired:
        print(json.dumps({'status':'UNKNOWN_CPU_METADATA_PROBE','owned_container_name':cmds[1][cmds[1].index('--name')+1],
                          'automatic_retry':False,'instruction':'Inspect this owned container before any repeat; no GPU device was supplied'}));return 1
    if r.returncode:
        print(json.dumps({'status':'FAILED_CPU_METADATA_PROBE','exit_code':r.returncode,'stderr':r.stderr[:2000],'automatic_retry':False}));return 1
    data=json.loads(r.stdout);data.update(image=IMAGE,status='METADATA_CHECKED_NOT_TARGET_INFERENCE',generation_requests=0)
    print(json.dumps(data,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
