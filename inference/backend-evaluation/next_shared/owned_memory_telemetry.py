"""Read-only diagnostics of a caller-verified owned CID/PID. Never an admission gate."""
from collections import deque
import os,re,time
from pathlib import Path


def bounded(path):
    with Path(path).open('r') as f:
        value=f.read(16385)
    if len(value)>16384:raise ValueError('TELEMETRY_FILE_LIMIT')
    return value


def process_start(proc):
    raw=bounded(proc/'stat');return raw.rsplit(')',1)[1].split()[19]


def snapshot(cid,pid,proc_root=Path('/proc'),cgroup_root=Path('/sys/fs/cgroup'),statvfs=os.statvfs):
    if not isinstance(cid,str) or re.fullmatch('[0-9a-f]{64}',cid) is None or type(pid) is not int or pid<=0:
        raise ValueError('FIXED_OWNED_CID_AND_RUNNING_PID_REQUIRED')
    proc=proc_root/str(pid);start=process_start(proc)
    rows=bounded(proc/'cgroup').splitlines();paths=[x[3:] for x in rows if x.startswith('0::')]
    if len(paths)!=1 or paths[0] not in ('/docker/'+cid,'/system.slice/docker-'+cid+'.scope'):
        raise ValueError('OWNED_CGROUP_V2_PATH_NOT_CONFIRMED')
    directory=cgroup_root/paths[0].lstrip('/')
    if directory.is_symlink() or any(x.is_symlink() for x in directory.parents if x!=cgroup_root.parent):
        raise ValueError('CGROUP_SYMLINK_NOT_PERMITTED')
    out={'status':'OBSERVED','cid':cid,'pid':pid,'starttime':start,'admission_gate':False}
    try:
        numbers={}
        for name in ['memory.current','memory.peak','memory.max','memory.swap.current','memory.swap.max']:
            value=bounded(directory/name).strip()
            if value!='max' and not value.isdecimal():raise ValueError('CGROUP_NUMBER_INVALID')
            numbers[name]=int(value) if value!='max' else value
        selected={}
        for name in ['memory.events','memory.stat']:
            values={}
            for line in bounded(directory/name).splitlines():
                key,value=line.split()
                if name=='memory.events' or key in {'anon','file','shmem','kernel','pagetables','sock','slab'}:
                    if not value.isdecimal():raise ValueError('CGROUP_STAT_INVALID')
                    values[key]=int(value)
            selected[name]=values
        out['cgroup']={'status':'OBSERVED',**numbers,**selected,'memory.pressure':bounded(directory/'memory.pressure')[:2048]}
    except Exception as exc:out['cgroup']={'status':'UNAVAILABLE','error_class':type(exc).__name__}
    try:
        # Fixed path through the verified process's root, no setns/exec/mount or fallback.
        v=statvfs(proc/'root/jit-cache');total=v.f_blocks*v.f_frsize
        if total!=512<<20:raise ValueError('FIXED_JIT_TMPFS_SIZE_NOT_CONFIRMED')
        out['jit_cache']={'status':'OBSERVED','total_bytes':total,'used_bytes':(v.f_blocks-v.f_bfree)*v.f_frsize,
            'available_bytes':v.f_bavail*v.f_frsize,'scope':'shared AITER+Triton tmpfs, not separate directory sizes'}
    except Exception as exc:out['jit_cache']={'status':'UNAVAILABLE','error_class':type(exc).__name__}
    if process_start(proc)!=start or bounded(proc/'cgroup').splitlines()!=rows:
        raise ValueError('PROCESS_IDENTITY_CHANGED_DURING_TELEMETRY')
    return out


class OwnedMemoryTelemetry:
    def __init__(self,probe=snapshot):
        self.probe=probe;self.rows=deque(maxlen=32);self.last=None;self.count=0;self.high_water={}
    def observe(self,cid,pid,now):
        if self.last is not None and now-self.last<1:return
        self.last=now;self.count+=1
        try:value=self.probe(cid,pid)
        except Exception as exc:value={'status':'UNAVAILABLE','error_class':type(exc).__name__,'admission_gate':False}
        row={'monotonic':now,'value':value};self.rows.append(row)
        for section,key in [('cgroup','memory.current'),('cgroup','memory.peak'),('cgroup','memory.swap.current'),('jit_cache','used_bytes')]:
            n=value.get(section,{}).get(key)
            if type(n) is int:self.high_water[section+'.'+key]=max(n,self.high_water.get(section+'.'+key,0))
    def snapshot(self):return {'admission_gate':False,'sample_count':self.count,'max_saved_samples':32,
        'sampled_high_water':dict(self.high_water),'samples':list(self.rows),'unavailable_is_not_zero':True}
