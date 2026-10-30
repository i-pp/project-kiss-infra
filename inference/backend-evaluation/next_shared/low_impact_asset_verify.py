"""Full SHA verification with bounded per-FD read hints/rate.
No model or host operation on import; no cache eviction or baseline reset.
"""
import hashlib,os,re,stat,time
from pathlib import Path
from fixed_trial_assets import Blocked,manifest,safe_path
BUFFER=1<<20
RATE=256<<20
BUDGET_SECONDS=240


def identity(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def verify(directory,check=lambda:None,report=lambda row:None,*,clock=time.monotonic,sleep=time.sleep,
           advise=None,release=None,manifest_fn=manifest):
    started=clock()
    release=os.uname().release if release is None else release
    m=re.match(r'(\d+)\.(\d+)',release)
    hint_enabled=bool(m and tuple(map(int,m.groups()))>=(6,3) and hasattr(os,'POSIX_FADV_NOREUSE') and hasattr(os,'posix_fadvise'))
    hint_status='AVAILABLE_EFFECT_NOT_GUARANTEED' if hint_enabled else 'UNAVAILABLE_NO_EFFECT_ASSUMED'
    advise=getattr(os,'posix_fadvise',None) if advise is None else advise
    directory=safe_path(directory);spec=manifest_fn();allowed={r['name'] for r in spec['required_files']}|{'acquisition.json'}
    if set(p.name for p in directory.iterdir())-allowed:raise Blocked('UNREVIEWED_MODEL_DIRECTORY_FILES')
    total_required=sum(row['bytes'] for row in spec['required_files'])
    estimate=total_required/RATE
    if estimate>BUDGET_SECONDS:raise Blocked('ASSET_PACING_ESTIMATE_EXCEEDS240_SECONDS')
    report({'phase':'ASSET_VERIFY','event':'plan','files':len(spec['required_files']),
            'required_bytes':total_required,'nominal_paced_read_seconds':estimate,
            'asset_deadline_seconds':BUDGET_SECONDS,'rate_limit_bytes_per_second':RATE,
            'buffer_bytes':BUFFER,'noreuse_status':hint_status,'noreuse_is_not_cache_eviction':True})
    start=started;total=0;last_report=-1;fingerprints=[]
    def guard():
        check()
        if clock()-start>=BUDGET_SECONDS:raise Blocked('ASSET_VERIFY240_SECONDS_EXCEEDED')
    for row in spec['required_files']:
        guard();path=safe_path(directory/row['name']);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size!=row['bytes']:raise Blocked('MODEL_FILE_SIZE_MISMATCH')
            # An access-pattern hint only. Never DONTNEED/WILLNEED/drop_caches.
            if hint_enabled:
                try:
                    advise(fd,0,0,os.POSIX_FADV_NOREUSE);hint_status='ACCEPTED_EFFECT_NOT_GUARANTEED'
                except OSError as exc:
                    # Keep the same bounded reader/rate/guards, no substitute advice.
                    hint_enabled=False;hint_status='REJECTED_'+type(exc).__name__+'_EFFECT_NOT_ASSUMED'
            h=hashlib.sha256();offset=0
            report({'phase':'ASSET_VERIFY','event':'file_start','file':row['name'],'bytes_expected':row['bytes'],
                    'identity':identity(before),'noreuse_status':hint_status,'hint_effect':'NOT_GUARANTEED'})
            while True:
                guard();block=os.read(fd,BUFFER)
                if not block:break
                h.update(block);offset+=len(block);total+=len(block)
                if offset>row['bytes']:raise Blocked('MODEL_FILE_GREW_DURING_HASH')
                guard()
                if clock()-last_report>=1:
                    report({'phase':'ASSET_VERIFY','event':'progress','file':row['name'],'file_bytes_read':offset,
                            'total_bytes_read':total,'elapsed_seconds':clock()-start});last_report=clock()
                target=start+total/RATE
                while clock()<target:
                    guard();remaining=target-clock()
                    if remaining>0:sleep(min(.05,remaining))
            after=os.fstat(fd)
            if (offset!=row['bytes'] or identity(before)!=identity(after)
                    or identity(after)!=identity(os.stat(path,follow_symlinks=False))):raise Blocked('MODEL_FILE_CHANGED_WHILE_HASHING')
            if h.hexdigest()!=row['sha256']:raise Blocked('MODEL_FILE_SHA256_MISMATCH')
            fingerprints.append((str(path),before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns))
            report({'phase':'ASSET_VERIFY','event':'file_verified','file':row['name'],'bytes_hashed':offset,'sha256':h.hexdigest()})
        finally:os.close(fd)
    guard();report({'phase':'ASSET_VERIFY','event':'all_verified','files':len(fingerprints),
                    'bytes_hashed':total,'elapsed_seconds':clock()-start,'buffer_bytes':BUFFER,'rate_limit_bytes_per_second':RATE})
    return fingerprints
