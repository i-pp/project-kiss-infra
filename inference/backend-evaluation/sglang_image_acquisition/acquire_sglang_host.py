"""Fixed official SGLang image acquisition, human host only. Never runs an image."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
DIGEST = 'sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230'
IMAGE = 'rocm/sgl-dev@' + DIGEST
PUBLISHED_COMPRESSED_BYTES = 13667503350
PULL_SECONDS = 1800
SHA = re.compile(r'sha256:[0-9a-f]{64}')

class Blocked(RuntimeError): pass
class MissingImage(Blocked): pass
class Unknown(RuntimeError): pass


def safe_path(path):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in [p,*p.parents]):
        raise Blocked('NON_SYMLINK_ABSOLUTE_PATH_REQUIRED')
    return p


def private_dir(path):
    p = safe_path(path)
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = p.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700:
        raise Blocked('PRIVATE_OWNER_DIRECTORY_REQUIRED')
    return p


def exclusive_json(path, data):
    p = safe_path(path)
    fd = os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    directory = os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)


def private_profile(path):
    fd = os.open(safe_path(path),os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        s = os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o600:
            raise Blocked('PROFILE_OWNER_MODE0600_REQUIRED')
        raw = f.read(65537)
    if len(raw)>65536: raise Blocked('PROFILE_TOO_LARGE')
    return safe_path(json.loads(raw)['orchestrator_root'])


def installed_context():
    # Fixed deployment layout, never an operator-selected import directory.
    if ROOT.parent.name != 'backend-evaluation': raise Blocked('INSTALLED_FIXED_LAYOUT_REQUIRED')
    repo = ROOT.parents[2]
    if ROOT != repo/'inference/backend-evaluation/sglang_image_acquisition':
        raise Blocked('INSTALLED_FIXED_LAYOUT_REQUIRED')
    helper = safe_path(ROOT.parent/'host_trial')
    if not (helper/'host_strata_trial.py').is_file(): raise Blocked('FIXED_HOST_GUARD_MISSING')
    sys.path.insert(0,str(helper))
    from host_strata_trial import host_guard
    orchestrator = private_profile(repo/'agents/local_llm/.runtime/router-host-profile.json')
    def guard():
        if os.getuid()==0 or not sys.stdin.isatty(): raise Blocked('NONROOT_HUMAN_TTY_REQUIRED')
        return host_guard(orchestrator)
    return repo,guard


class Journal:
    def __init__(self,parent):
        self.parent=private_dir(parent)
        self.run=private_dir(self.parent/('run-'+uuid.uuid4().hex))
        self.started=time.monotonic()
        self.fd=os.open(self.run/'progress.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_APPEND,0o600)
    def event(self,stage,**data):
        row={'elapsed_seconds':round(time.monotonic()-self.started,3),'stage':stage,**data}
        os.write(self.fd,(json.dumps(row,ensure_ascii=False)+'\n').encode());os.fsync(self.fd)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    def write(self,name,data): exclusive_json(self.run/name,data)
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None


class Docker:
    """Only daemon version, exact image inspect, and one fixed pull are allowed."""
    def __init__(self,guard,journal,clock=time.monotonic,sleep=time.sleep):
        self.guard=guard;self.journal=journal;self.clock=clock;self.sleep=sleep
        self.config=private_dir(journal.run/'docker-config')
        self.clients_reaped=True
    def command(self,args,name,seconds):
        allow=[(['version','--format','{{.Server.Version}}'],'preflight',10),
               (['image','inspect',IMAGE],'inspect',10),
               (['pull','--quiet',IMAGE],'pull',PULL_SECONDS)]
        if (args,name,seconds) not in allow:raise Blocked('NON_FIXED_DOCKER_OPERATION')
        self.guard();self.journal.event(name+'_begin');start=self.clock()
        stdout_path=self.journal.run/(name+'-'+uuid.uuid4().hex+'.stdout')
        stderr_path=self.journal.run/(name+'-'+uuid.uuid4().hex+'.stderr')
        outfd=os.open(stdout_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        errfd=os.open(stderr_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        proc=None
        try:
            try:
                proc=subprocess.Popen(['/usr/bin/docker','--host','unix:///var/run/docker.sock',*args],
                                      stdout=outfd,stderr=errfd,
                                      env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','DOCKER_CONFIG':str(self.config)})
                next_progress=start+2
                while proc.poll() is None:
                    now=self.clock()
                    if now-start>=seconds:raise TimeoutError('FIXED_DOCKER_DEADLINE')
                    if os.fstat(outfd).st_size>2<<20 or os.fstat(errfd).st_size>2<<20:
                        raise Unknown('DOCKER_OUTPUT_LIMIT')
                    if now>=next_progress:
                        self.journal.event(name+'_waiting',seconds=round(now-start,1));next_progress=now+2
                    self.sleep(.1)
                proc.wait(timeout=5)
            except BaseException as exc:
                if proc is None:
                    self.clients_reaped=False
                    raise Unknown('DOCKER_SPAWN_OUTCOME_UNKNOWN_NO_HANDLE') from exc
                try:proc.kill()
                except ProcessLookupError:pass
                except BaseException:self.clients_reaped=False
                try:proc.wait(timeout=5)
                except BaseException:self.clients_reaped=False
                raise Unknown('DOCKER_REQUEST_UNKNOWN_CLIENT_REAP_'+str(self.clients_reaped)) from exc
        finally:
            os.fsync(outfd);os.fsync(errfd);os.close(outfd);os.close(errfd)
        if stdout_path.stat().st_size>2<<20 or stderr_path.stat().st_size>2<<20:raise Unknown('DOCKER_RESPONSE_LIMIT')
        stdout=stdout_path.read_text(errors='replace');stderr=stderr_path.read_text(errors='replace')
        self.journal.event(name+'_cli_exit',exit_code=proc.returncode)
        if proc.returncode:
            pattern=r'(?:Error response from daemon: |Error: )?No such image: '+re.escape(IMAGE)+r'\s*'
            if name=='inspect' and re.fullmatch(pattern,stderr):raise MissingImage('FIXED_IMAGE_ABSENT')
            if name=='pull':raise Unknown('PULL_FAILED_NO_RETRY')
            raise Blocked('DOCKER_READ_FAILED_'+str(proc.returncode))
        return stdout
    def preflight(self):
        v=self.command(['version','--format','{{.Server.Version}}'],'preflight',10).strip()
        if not re.fullmatch(r'\d+\.\d+\.\d+(?:[a-zA-Z0-9.+_-]*)?',v):raise Blocked('DAEMON_VERSION_UNKNOWN')
        return v
    def inspect(self):
        d=json.loads(self.command(['image','inspect',IMAGE],'inspect',10))
        if not isinstance(d,list) or len(d)!=1:raise Blocked('EXACT_IMAGE_INSPECT_SCHEMA')
        return d[0]
    def pull_once(self):self.command(['pull','--quiet',IMAGE],'pull',PULL_SECONDS)


def verify_metadata(d):
    if not isinstance(d,dict) or not isinstance(d.get('Id'),str) or not SHA.fullmatch(d['Id']):raise Blocked('IMAGE_ID_UNKNOWN')
    if d.get('Os')!='linux' or d.get('Architecture')!='amd64':raise Blocked('IMAGE_PLATFORM_MISMATCH')
    repos=d.get('RepoDigests')
    if not isinstance(repos,list) or any(not isinstance(x,str) for x in repos) or IMAGE not in repos:raise Blocked('FIXED_REPO_DIGEST_NOT_PRESENT')
    if type(d.get('Size')) is not int or d['Size']<=0:raise Blocked('UNPACKED_SIZE_UNKNOWN')
    config=d.get('Config')
    if not isinstance(config,dict):raise Blocked('IMAGE_CONFIG_SCHEMA')
    labels=config.get('Labels') or {}
    if not isinstance(labels,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in labels.items()):raise Blocked('IMAGE_LABELS_SCHEMA')
    return {'image_id':d['Id'],'repo_digests':repos,'os':d['Os'],'architecture':d['Architecture'],
            'unpacked_size_bytes':d['Size'],'labels':labels}


def acquire(docker,journal):
    report={'status':'STARTING','image_ref':IMAGE,'published_compressed_bytes':PUBLISHED_COMPRESSED_BYTES,
            'pull_requests':0,'image_runs':0,'gpu_operations':0,'container_operations':0,
            'source_dependency_inspection':'NOT_PERFORMED_METADATA_ONLY'}
    pull_intended=False
    try:
        report['docker_server_version']=docker.preflight()
        try:image=docker.inspect()
        except MissingImage:
            report['project_filesystem_free_before_pull']=shutil.disk_usage(journal.parent).free
            if report['project_filesystem_free_before_pull']<64*(1<<30):
                raise Blocked('PROJECT_FILESYSTEM_FREE_BELOW64GIB')
            exclusive_json(journal.parent/'pull-intent.json',{'image_ref':IMAGE,'run':str(journal.run),
                           'state':'PULL_INTENT_NO_RETRY','daemon_may_continue_on_client_exit':True})
            pull_intended=True
            journal.write('intent.json',{'image_ref':IMAGE,'action':'ONE_PULL_METADATA_ONLY','limit_seconds':PULL_SECONDS})
            journal.event('pull_intent_durable')
            report['pull_requests']=1
            try:docker.pull_once()
            except BaseException as exc:raise Unknown('PULL_OUTCOME_UNKNOWN_NO_RETRY') from exc
            image=docker.inspect()
        report['metadata']=verify_metadata(image)
        report['status']='ACQUIRED_METADATA_VERIFIED' if report['pull_requests'] else 'EXISTING_EXACT_IMAGE_METADATA_VERIFIED'
        journal.event('metadata_verified',pull_requests=report['pull_requests'])
        return report
    except BaseException as exc:
        # Any interruption after durable intent leaves pull potentially active in daemon.
        unknown=isinstance(exc,Unknown) or pull_intended
        report.update(status='UNKNOWN_NO_RETRY' if unknown else 'BLOCKED_NO_PULL_RETRY',
                      reason=type(exc).__name__+':'+str(exc),client_reaped=getattr(docker,'clients_reaped',None))
        raise
    finally:journal.write('receipt.json',report)


def terminate(signum,frame):raise KeyboardInterrupt('TERMINATION_REQUESTED')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--acquire-human-approved',action='store_true');a=p.parse_args()
    if not a.acquire_human_approved:
        print(json.dumps({'status':'PREPARED_INDIVIDUAL_APPROVAL_REQUIRED','image_ref':IMAGE,
                          'published_compressed_bytes':PUBLISHED_COMPRESSED_BYTES,'pull_requests':0,'image_runs':0}));return 0
    signal.signal(signal.SIGTERM,terminate)
    repo,guard=installed_context();guard()
    os.umask(0o077)
    journal=Journal(repo/'agents/local_llm/.runtime/backend-runtime/sglang-image-acquisition')
    try:
        result=acquire(Docker(guard,journal),journal)
        print(json.dumps({'status':result['status'],'pull_requests':result['pull_requests'],
                          'receipt':str(journal.run/'receipt.json'),'image_runs':0}));return 0
    finally:journal.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:
        print(json.dumps({'status':'BLOCKED_OR_UNKNOWN_NO_RETRY','reason':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(130 if isinstance(exc,KeyboardInterrupt) else 1)
