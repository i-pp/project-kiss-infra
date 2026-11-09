"""Host-only model management adapter bound to a fixed disposable container.

No listening socket is created. The endpoint is derived from inspected Docker
identity and never accepted from a user request. The Core image excludes this.
"""
from __future__ import annotations
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from inference.local_platform.model_management import ModelError

IMAGE='sha256:d4ae7c574945c7432c8c02ae63fa81ad555854d9fcbc29d02542a4dd69833a85'


def docker(*args,timeout=15):
    out=subprocess.run(['docker','--host=unix:///var/run/docker.sock',*args],capture_output=True,text=True,timeout=timeout)
    if out.returncode: raise ModelError('fixed acceptance Docker operation failed: '+args[0])
    return out.stdout.strip()


def fixed_engine_identity(name,owner,model_store):
    identity={'name':name,'owner':str(owner),'image':IMAGE,'model_store':str(Path(model_store).resolve())}
    return 'ollama:fixed-acceptance:'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()


class FixedContainerHTTP:
    def __init__(self,cid,*,name,owner,provider_root,weights,network,references,cli=docker):
        if not re.fullmatch('[0-9a-f]{64}',cid):raise ModelError('full fixed container ID required')
        self.cid,self.name,self.owner,self.network,self.cli=cid,name,str(owner),network,cli
        self.provider_root,self.weights=Path(provider_root).resolve(),Path(weights).resolve()
        self.references=frozenset(references)
        self.identity=fixed_engine_identity(name,owner,self.provider_root/'store')
    def inspect(self):
        info=json.loads(self.cli('inspect',self.cid))[0]; h,c=info['HostConfig'],info['Config']
        expected_mounts={'/weights':(str(self.weights),False),'/input':(str(self.provider_root/'input'),False),'/store':(str(self.provider_root/'store'),True)}
        mounts={m['Destination']:(m['Source'],m['RW']) for m in info['Mounts']}
        devices=[{'PathOnHost':p,'PathInContainer':p,'CgroupPermissions':'rwm'} for p in ['/dev/kfd','/dev/dri/renderD128']]
        if (info['Id']!=self.cid or info['Name']!='/'+self.name or info['Image']!=IMAGE
            or c.get('Labels',{}).get('aceis.inference.owner')!=self.owner or c.get('User')!='1000:1000'
            or h.get('Privileged') is not False or h.get('ReadonlyRootfs') is not True
            or h.get('CapDrop')!=['ALL'] or h.get('CapAdd') or h.get('SecurityOpt')!=['no-new-privileges:true']
            or h.get('PortBindings') or any(info['NetworkSettings'].get('Ports',{}).values())
            or h.get('PidMode','')!='' or h.get('IpcMode')!='private' or h.get('RestartPolicy',{}).get('Name')!='no'
            or h.get('GroupAdd')!=['990'] or h.get('Devices')!=devices or h.get('DeviceRequests')
            or h.get('Memory')!=32*2**30 or h.get('MemorySwap')!=32*2**30 or h.get('NanoCpus')!=8*10**9 or h.get('PidsLimit')!=512
            or h.get('NetworkMode')!=self.network or set(info['NetworkSettings']['Networks'])!={self.network}
            or mounts!=expected_mounts or h.get('Tmpfs')!={'/tmp':'rw,noexec,nosuid,nodev,size=512m'}):
            raise ModelError('fixed acceptance engine identity/security mismatch')
        expected_env={'OLLAMA_HOST=0.0.0.0:30000','OLLAMA_MODELS=/store','OLLAMA_MAX_LOADED_MODELS=1','OLLAMA_NUM_PARALLEL=1','OLLAMA_NO_CLOUD=1'}
        if not expected_env<=set(c.get('Env') or []):raise ModelError('fixed acceptance engine environment mismatch')
        if type(info['State'].get('Running')) is not bool:raise ModelError('unknown engine state')
        return info
    def __call__(self,method,path,body=None):
        allowed={("GET","/api/tags"),("GET","/api/ps"),("GET","/api/version")}
        if (method,path)==('POST','/api/pull'):
            if type(body) is not dict or set(body)!={'model','stream'} or body['model'] not in self.references or body['stream'] is not False:
                raise ModelError('only verified fixed acceptance references can be pulled')
        elif (method,path) not in allowed or body is not None:
            raise ModelError('unsupported fixed acceptance management operation')
        info=self.inspect()
        if not info['State']['Running']:raise ModelError('fixed acceptance engine is stopped')
        address=info['NetworkSettings']['Networks'][self.network]['IPAddress']
        ip=ipaddress.ip_address(address)
        if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ModelError('private inspected engine endpoint required')
        conn=http.client.HTTPConnection(str(ip),30000,timeout=900 if path=='/api/pull' else 5)
        try:
            conn.request(method,path,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json'})
            response=conn.getresponse(); raw=response.read(1024*1024+1)
            if response.status!=200 or len(raw)>1024*1024:raise ModelError('fixed engine management response rejected')
            value=json.loads(raw)
            if not isinstance(value,dict) or 'error' in value:raise ModelError('fixed engine rejected management operation')
            return value
        finally:conn.close()
