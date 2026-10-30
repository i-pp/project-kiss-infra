"""Explicit human-host artifact bootstrap only; never launches Strata or a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.parse
from host_strata_trial import host_guard,private_dir,private_write
import assets

ENGINE_URL='https://github.com/Niko1221/Strata/releases/download/v0.2.7/strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz'
HOSTS={'github.com','codeload.github.com','objects.githubusercontent.com','release-assets.githubusercontent.com','files.pythonhosted.org'}


def allowed(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):
        raise ValueError('Unreviewed artifact origin')
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        allowed(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url,target,max_bytes,expected_sha=None,expected_bytes=None,opener=None):
    allowed(url);target=Path(target)
    if target.exists() or target.is_symlink():raise ValueError('Fresh artifact target required; no blind retry/overwrite')
    h=hashlib.sha256();n=0;deadline=time.monotonic()+300
    opener=opener or urllib.request.build_opener(Redirects())
    req=urllib.request.Request(url,headers={'User-Agent':'AceIS-human-reviewed-artifact-bootstrap'})
    try:
        with opener.open(req,timeout=30) as response,target.open('xb') as out:
            while True:
                b=response.read(1048576)
                if not b:break
                if time.monotonic()>deadline:raise TimeoutError('Artifact transfer deadline reached')
                n+=len(b)
                if n>max_bytes:raise ValueError('Artifact exceeded reviewed compressed-byte budget')
                h.update(b);out.write(b)
        if expected_bytes is not None and n!=expected_bytes:raise ValueError('Artifact size differs')
        if expected_sha is not None and h.hexdigest()!=expected_sha:raise ValueError('Artifact digest differs')
        return {'bytes':n,'sha256':h.hexdigest(),'path':str(target)}
    except BaseException:
        # Retain the partial under its unique new operator directory for evidence; never execute it.
        raise


def unpack(archive,dest,max_bytes,strip_root=False):
    dest=Path(dest)
    if dest.exists():raise ValueError('Fresh extraction directory required')
    dest.mkdir(mode=0o700)
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        if len(members)>50000 or sum(x.size for x in members)>max_bytes:raise ValueError('Expanded artifact budget exceeded')
        prefix=None
        if strip_root:
            roots={PurePosixPath(x.name).parts[0] for x in members if PurePosixPath(x.name).parts}
            if len(roots)!=1:raise ValueError('Source archive must have one top directory')
            prefix=next(iter(roots))
        selected=[]
        for m in members:
            p=PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or m.isdev() or m.isfifo() or m.islnk():raise ValueError('Unsafe archive member')
            if prefix:
                parts=p.parts[1:]
                if not parts:continue
                m=m.replace(name=str(PurePosixPath(*parts)),deep=False)
            selected.append(m)
        # Python data filter rejects escaped links and strips dangerous extraction metadata.
        tf.extractall(dest,members=selected,filter='data')
    return dest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acquire-human-approved',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args()
    if not a.acquire_human_approved:
        print(json.dumps({'status':'PREPARED_INDIVIDUAL_APPROVAL_REQUIRED','engine_bytes':169966238,'weight_downloads':0,'software_executions':0}));return 0
    if a.output is None or a.output.exists():raise ValueError('Choose a new operator-owned output directory')
    if sys.version_info[:2]!=(3,14):raise ValueError('Prepared wheel lock is for regular Linux x86_64 Python3.14 only; no automatic version fallback')
    if os.uname().machine!='x86_64':raise ValueError('Prepared architecture is x86_64 only')
    repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'agents/local_llm'))
    from endpoint_config import private_json
    profile=private_json(repo/'agents/local_llm/.runtime/router-host-profile.json')
    host_guard(profile['orchestrator_root']);os.umask(0o077)
    root=private_dir(a.output);downloads=private_dir(root/'downloads')
    if shutil.disk_usage(root).free<8*(1<<30):raise ValueError('At least8GiB bootstrap free disk required; pack later requires100GiB')
    report={'status':'ACQUIRING_ONLY_NO_ENGINE_EXECUTION','files':[],'model_downloads':0,'engine_executions':0}
    try:
        report['files'].append(fetch(ENGINE_URL,downloads/'engine.tar.gz',169966238,assets.ENGINE_SHA,169966238))
        for name,repo_name,commit,expanded in [('strata-source','Niko1221/Strata',assets.COMMIT,256<<20),('llama-source','ggml-org/llama.cpp',assets.LLAMA_COMMIT,512<<20)]:
            f=downloads/(name+'.tar.gz')
            report['files'].append(fetch('https://github.com/'+repo_name+'/archive/'+commit+'.tar.gz',f,64<<20))
            unpack(f,root/name,expanded,strip_root=True)
        # Bundle expansion is only data extraction; entrypoint selection/execution stays pending operator review.
        unpack(downloads/'engine.tar.gz',root/'engine-bundle',4<<30)
        from publisher_verify import verify_signed_bundle
        found=list((root/'engine-bundle').rglob('engine-component.json'))
        if len(found)!=1:raise ValueError('Exactly one publisher engine component required')
        report['engine_integrity']=verify_signed_bundle(found[0].parent)
        report['engine_root']=str(found[0].parent)
        base=Path(__file__).parent
        assets.verify_python_tree(root/'strata-source',json.loads((base/'strata-source-files.json').read_text()))
        assets.verify_python_tree(root/'llama-source',json.loads((base/'gguf-source-files.json').read_text()),'gguf-py')
        wheels=private_dir(root/'wheels')
        for row in json.loads((base/'wheels-cp314.json').read_text()):
            report['files'].append(fetch(row['url'],wheels/row['name'],row['bytes'],row['sha256'],row['bytes']))
        child_env={'PATH':str(Path(sys.executable).parent)+':/usr/bin:/bin','HOME':str(root),
                   'PYTHONNOUSERSITE':'1','PYTHONPATH':'','PIP_CONFIG_FILE':'/dev/null',
                   'PIP_NO_INPUT':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'}
        subprocess.run([sys.executable,'-m','venv',str(root/'venv')],check=True,timeout=90,env=child_env)
        subprocess.run([str(root/'venv/bin/python'),'-m','pip','install','--no-index','--find-links',str(wheels),
                        '--only-binary=:all:','--require-hashes','--no-deps','-r',str(base/'requirements-cp314.lock')],check=True,timeout=120,env=child_env)
        report['status']='ACQUIRED_ENGINE_MANIFEST_AND_NOTICES_REVIEW_PENDING'
    finally:private_write(root/'acquisition.json',report)
    print(json.dumps(report,indent=2));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print(json.dumps({'status':'BLOCKED_NO_AUTO_RETRY','reason':type(e).__name__+':'+str(e)[:300]}),file=sys.stderr);raise SystemExit(1)
