"""Separately approved fixed retry02: verify old pilot, build a fresh full pack.

No acquisition, namespace, service management, alternate endpoint, or generic CLI.
Only the installed human-host entry point may execute the reviewed trial.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import time

import assets
import host_strata_trial as h
from notice_review import read_bound
from owned_process import GIB, OwnedProcessRunner

PRIOR_RUN='strata-20261030T072213Z-3b931781'
PRIOR_SHA='94a89fedbe92d5cca1d614fa02413b6d70508909fe0f9e5e5cff5cab502d6bbc'
PILOT_IDENTITY_SHA='36cf730d13c9f13eeba6f3b4f84b5284762c40b3bd832573f7739e3120a6b8b6'
SCOPE='STRATA_RETRY02_AFTER_ACCIDENTAL_INTERRUPT'
APPROVAL_NAME='strata-retry02-approval-20261030.json'
IDENTITY_NAME='strata-retry02-pilot-identity-20261030.json'
INTENT_NAME='strata-retry02-intent-20261030.json'
CONSUMED_REFS={'Sentinel_710bf418f4948191a099de29ea9adcbc','Sentinel_13c26996c6708191845863ffac804945'}
PILOT_NAMES={'dense.bin','embd.bin','experts.bin','experts.json','manifest.json'}


def validate_prior(data):
    expected={'status':'FAILED','environment':'NOT_RUN','quality':'UNASSESSED',
              'generation_requests':0,'completed_generations':0,'automatic_retry':False,
              'code_executed':False,'source_metadata_unchanged':True,
              'reason':'Blocked:full_build:INTERRUPTED'}
    if any(type(data.get(k)) is not type(v) or data[k]!=v for k,v in expected.items()):
        raise h.Blocked('FIXED_INTERRUPTED_UNGENERATED_PRIOR_REQUIRED')
    restoration=data.get('restoration')
    states={'kiss-b3-gpt-oss-120b':'unloaded','kiss-b3-qwen-coder-next':'unloaded',h.MODEL:'loaded'}
    if not isinstance(restoration,dict) or restoration.get('status')!='RESTORED' or restoration.get('model_states')!=states:
        raise h.Blocked('PRIOR_30B_RESTORATION_NOT_CONFIRMED')
    return data


def validate_approval(data):
    fixed={'approved':True,'scope':SCOPE,'prior_summary_sha256':PRIOR_SHA,
           'pilot_identity_sha256':PILOT_IDENTITY_SHA,'attempt_limit':1,'generation_limit':1,
           'whole_seconds':2400,'cumulative_data_limit_bytes':120*GIB,
           'per_run_data_limit_bytes':70*GIB,'start_free_bytes':100*GIB,'minimum_free_bytes':32*GIB}
    if any(type(data.get(k)) is not type(v) or data[k]!=v for k,v in fixed.items()):
        raise h.Blocked('SEPARATE_RETRY02_APPROVAL_AND_FIXED_LIMITS_REQUIRED')
    ref=data.get('approval_reference')
    if not isinstance(ref,str) or not ref.startswith('Sentinel_') or ref in CONSUMED_REFS:
        raise h.Blocked('NEW_RETRY02_APPROVAL_REFERENCE_REQUIRED')
    if not isinstance(data.get('owner_approval_verified_at_utc'),str) or not data['owner_approval_verified_at_utc']:
        raise h.Blocked('OWNER_RETRY02_APPROVAL_NOT_VERIFIED')
    return data


def no_symlink_ancestry(path):
    p=Path(path)
    if not p.is_absolute() or any(x.is_symlink() for x in [p,*p.parents]):
        raise h.Blocked('SYMLINK_OR_RELATIVE_REPLAY_PATH')
    return p


def inventory_metadata(root):
    root=no_symlink_ancestry(root)
    if not root.is_dir():raise h.Blocked('REPLAY_DIRECTORY_MISSING')
    result={}
    for p in root.rglob('*'):
        if p.is_symlink():raise h.Blocked('SYMLINK_IN_REPLAY_PACK')
        s=p.lstat()
        if stat.S_ISDIR(s.st_mode):continue
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise h.Blocked('NONREGULAR_OR_LINKED_REPLAY_PACK')
        result[str(p.relative_to(root))]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    return result


def verify_inventory(root,rows,monitor=lambda:None):
    """Read only: full fixed file inventory/SHA; check stable inode/size/mtime."""
    before=inventory_metadata(root);expected={};next_monitor=0
    if not isinstance(rows,list) or not rows:raise h.Blocked('PILOT_IDENTITY_FILES_REQUIRED')
    for row in rows:
        rel=row.get('path');rp=Path(rel) if isinstance(rel,str) else Path('/')
        if rp.is_absolute() or '..' in rp.parts or not rp.parts or rel in expected:
            raise h.Blocked('UNSAFE_OR_DUPLICATE_PILOT_IDENTITY')
        if type(row.get('bytes')) is not int or row['bytes']<0 or not re.fullmatch('[0-9a-f]{64}',row.get('sha256','')):
            raise h.Blocked('INVALID_PILOT_IDENTITY')
        expected[rel]=row
    if set(before)!=set(expected):raise h.Blocked('PILOT_EXACT_INVENTORY_MISMATCH')
    for rel,row in expected.items():
        if before[rel][2]!=row['bytes']:raise h.Blocked('PILOT_FILE_SIZE_MISMATCH')
        digest=hashlib.sha256();p=Path(root)/rel
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as f:
            s=os.fstat(f.fileno())
            if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)!=before[rel]:raise h.Blocked('PILOT_CHANGED_BEFORE_HASH')
            for chunk in iter(lambda:f.read(4<<20),b''):
                digest.update(chunk)
                if time.monotonic()>=next_monitor:
                    monitor();next_monitor=time.monotonic()+.5
        if digest.hexdigest()!=row['sha256']:raise h.Blocked('PILOT_FILE_HASH_MISMATCH')
    monitor()
    if inventory_metadata(root)!=before:raise h.Blocked('PILOT_CHANGED_DURING_HASH')
    return before


def directory_bytes(root):
    """Logical bytes, including retained partial data; no symlink traversal."""
    root=no_symlink_ancestry(root)
    if not root.is_dir():raise h.Blocked('BUDGET_ROOT_MISSING')
    total=0
    for here,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if not Path(here,d).is_symlink()]
        for name in files:
            p=Path(here,name);s=p.lstat()
            if stat.S_ISLNK(s.st_mode):continue
            if not stat.S_ISREG(s.st_mode):raise h.Blocked('BUDGET_NONREGULAR_FILE')
            total+=s.st_size
    return total


class CumulativeBudget:
    def __init__(self,roots,free_path,usage=None,measure=None):
        self.roots=tuple(no_symlink_ancestry(p) for p in roots)
        for i,p in enumerate(self.roots):
            if any(p==q or p.is_relative_to(q) or q.is_relative_to(p) for q in self.roots[:i]):
                raise h.Blocked('OVERLAPPING_BUDGET_ROOTS')
        self.free_path=Path(free_path);self.usage=usage or shutil.disk_usage;self.measure=measure or directory_bytes
    def sample(self,start=False):
        values=[self.measure(p) for p in self.roots];free=self.usage(self.free_path).free
        data={'cumulative_data_bytes':sum(values),'cumulative_root_bytes':dict(zip(map(str,self.roots),values)),
              'filesystem_free_bytes':free,'budget_mode':'soft sampled logical bytes; no hard cap'}
        problem=('CUMULATIVE_DATA_LIMIT' if sum(values)>120*GIB else
                 'START_FREE_DISK_BELOW100GIB' if start and free<100*GIB else
                 'FREE_DISK_BELOW32GIB' if free<32*GIB else None)
        return data,problem


class CumulativeRunner(OwnedProcessRunner):
    def __init__(self,*,budget,**kwargs):self.budget=budget;super().__init__(**kwargs)
    def _sample(self,*args,**kwargs):
        sample,problem=super()._sample(*args,**kwargs)
        extra,budget_problem=self.budget.sample();sample.update(extra)
        return sample,problem or budget_problem


class ReplayTrial(h.Trial):
    def __init__(self,repo,verified,coordinator,identity,runner_factory=None,started_at=None,**kwargs):
        self.identity=identity;self.prior=Path(repo)/'agents/local_llm/.runtime/backend-trials'/PRIOR_RUN
        self.pilot=self.prior/'pilot';self.software=Path(repo)/'.cache/backend-evaluation/strata-v027-e0152'
        self.budget=None;self.pilot_stamp=None;self.old_full_stamp=None
        def factory(**kw):
            self.budget=CumulativeBudget([self.prior,self.software,kw['run_dir']],kw['run_dir'])
            return (runner_factory(**kw) if runner_factory else CumulativeRunner(budget=self.budget,**kw))
        super().__init__(repo,verified,coordinator,runner_factory=factory,**kwargs)
        if started_at is not None:self.started=started_at
    def safety(self):
        sample=super().safety()
        data,problem=self.budget.sample()
        if problem:
            self.log('retry02_budget_abort',reason=problem,**data);raise h.Blocked(problem)
        self.remaining(1)
        return {**sample,**data}
    def before_unload(self):
        i=self.identity
        if (i.get('schema')!=1 or i.get('prior_run')!=PRIOR_RUN or i.get('prior_summary_sha256')!=PRIOR_SHA
                or i.get('pilot_relative')!='pilot' or i.get('full_reusable') is not False
                or {r.get('path') for r in i.get('files',[])}!=PILOT_NAMES):
            raise h.Blocked('FIXED_PILOT_IDENTITY_REQUIRED')
        no_symlink_ancestry(self.v['source'])
        data,problem=self.budget.sample(start=True)
        self.log('retry02_budget_preflight',**data)
        if problem:raise h.Blocked(problem)
        read_bound(self.prior/'pilot_verify.json',i['pilot_verify_sha256'],private=True)
        self.old_full_stamp=inventory_metadata(self.prior/'full')
        self.pilot_stamp=verify_inventory(self.pilot,i['files'],monitor=self.safety)
        h.validate_pack(self.pilot,1)
        self.log('reuse_pilot_verify_intent',pilot=str(self.pilot),pilot_identity_sha256=PILOT_IDENTITY_SHA)
        self.stage('pilot_verify',[sys.executable,'-B',str(self.v['source']/'tools/strata_pack.py'),'verify',
                   '--gguf',str(self.v['shards'][0]),'--out',str(self.pilot)])
        if inventory_metadata(self.pilot)!=self.pilot_stamp:raise h.Blocked('REUSED_PILOT_MODIFIED_BY_VERIFY')
        if inventory_metadata(self.prior/'full')!=self.old_full_stamp:raise h.Blocked('OLD_FULL_METADATA_CHANGED')
    def build_packs(self):
        full=self.run/'full'
        if full.exists() or full.is_symlink():raise h.Blocked('FRESH_FULL_OUTPUT_REQUIRED')
        try:
            self.stage('full_build',[sys.executable,'-B',str(self.v['source']/'tools/strata_pack.py'),'build',
                       '--gguf',str(self.v['shards'][0]),'--out',str(full),'--layers','48'])
            h.validate_pack(full,48)
            self.stage('full_verify',[sys.executable,'-B',str(self.v['source']/'tools/strata_pack.py'),'verify',
                       '--gguf',str(self.v['shards'][0]),'--out',str(full)])
            return full
        finally:
            if inventory_metadata(self.pilot)!=self.pilot_stamp or inventory_metadata(self.prior/'full')!=self.old_full_stamp:
                raise h.Blocked('RETAINED_PACK_METADATA_CHANGED')


def run_once(repo,verified,coordinator,approval,identity,trial_factory=ReplayTrial):
    if getattr(h,'PACK_HOOK_VERSION',None)!=1:raise h.Blocked('REVIEWED_PACK_HOOKS_REQUIRED')
    validate_approval(approval);coordinator.guard()
    marker=Path(repo)/'agents/local_llm/.runtime'/INTENT_NAME
    with coordinator.locked():
        coordinator.idle()
        h.private_write(marker,{'scope':SCOPE,'approval_reference':approval['approval_reference'],
            'prior_run':PRIOR_RUN,'prior_summary_sha256':PRIOR_SHA,'pilot_identity_sha256':PILOT_IDENTITY_SHA,
            'state':'ONE_APPROVED_ATTEMPT_INTENT','automatic_retry':False})
        for p,flags in [(marker,os.O_RDONLY|os.O_NOFOLLOW),(marker.parent,os.O_RDONLY|os.O_DIRECTORY)]:
            fd=os.open(p,flags)
            try:os.fsync(fd)
            finally:os.close(fd)
    h.RUN_STARTED=True
    return trial_factory(repo,verified,coordinator,identity).execute()


def main():
    entry_started=time.monotonic()
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--retry-human-approved',action='store_true');a=p.parse_args()
    if not a.retry_human_approved:
        print(json.dumps({'status':'PREPARED_RETRY02_APPROVAL_REQUIRED','generation_requests':0,'scope':SCOPE}));return 0
    here=Path(__file__).resolve();repo=here.parents[3]
    if here.parent!=repo/'inference/backend-evaluation/host_trial':raise h.Blocked('FIXED_INSTALLED_LAYOUT_REQUIRED')
    if getattr(h,'PACK_HOOK_VERSION',None)!=1:raise h.Blocked('REVIEWED_PACK_HOOKS_REQUIRED')
    rt=repo/'agents/local_llm/.runtime'
    validate_prior(json.loads(read_bound(rt/'backend-trials'/PRIOR_RUN/'summary.json',PRIOR_SHA,private=True)))
    approval=validate_approval(assets.private_record(rt/APPROVAL_NAME))
    identity=json.loads(read_bound(rt/IDENTITY_NAME,PILOT_IDENTITY_SHA,private=True))
    verified=assets.verify(rt/'strata-reviewed-assets-20261030.json',repo)
    def interrupted(signum,frame):raise KeyboardInterrupt('HOST_RETRY02_SIGNAL_'+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    os.umask(0o077)
    def trial_factory(repo,verified,coordinator,identity):
        return ReplayTrial(repo,verified,coordinator,identity,started_at=entry_started)
    result=run_once(repo,verified,h.Coordinator(repo,verified['record']),approval,identity,trial_factory=trial_factory)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status']=='COMPLETED' and result['restoration']!='UNKNOWN' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:
        print(json.dumps({'status':'UNKNOWN_NO_RETRY' if h.RUN_STARTED else 'BLOCKED_BEFORE_TRIAL',
            'reason':type(exc).__name__+':'+str(exc)[:400],'generation_requests':None if h.RUN_STARTED else 0,'automatic_retry':False}))
        raise SystemExit(1)
