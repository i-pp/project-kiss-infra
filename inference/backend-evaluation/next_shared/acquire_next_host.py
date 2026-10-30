"""Fixed Next checkpoint acquisition, only from a reviewed human host terminal."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.parse
import urllib.request
from fixed_trial_assets import Blocked, helpers, install_sigterm_handler, manifest, operator_record, safe_path

HOSTS={'huggingface.co','cdn-lfs.huggingface.co','cdn-lfs.hf.co',
       'cdn-lfs-us-1.hf.co','cdn-lfs-eu-1.hf.co','cas-bridge.xethub.hf.co','us.aws.cdn.hf.co'}


def allowed(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):
        raise Blocked('UNREVIEWED_REDIRECT_ORIGIN')


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        allowed(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_one(row,target,opener,deadline):
    """One HTTP request chain, no retries/resume, final name never overwritten."""
    d=manifest()
    fixed=next((r for r in d['required_files'] if r['name']==row['name']),None)
    if fixed!=row:raise Blocked('NOT_A_FIXED_ASSET')
    target=Path(target);partial=target.with_name(target.name+'.partial')
    if target.exists() or target.is_symlink() or partial.exists() or partial.is_symlink():raise Blocked('NO_OVERWRITE_OR_UNKNOWN_RETRY')
    url='https://huggingface.co/'+d['repo']+'/resolve/'+d['revision']+'/'+row['name']
    allowed(url)
    # Disable proxy and credentials inherited from arbitrary process environments.
    req=urllib.request.Request(url,headers={'User-Agent':'AceIS-fixed-Next-human-acquisition','Accept-Encoding':'identity'})
    h=hashlib.sha256();count=0
    fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:
        with opener.open(req,timeout=30) as response:
            if response.status!=200:raise Blocked('HTTP_NOT_200')
            length=response.headers.get('Content-Length')
            if length is not None and int(length)!=row['bytes']:raise Blocked('REMOTE_SIZE_MISMATCH')
            while True:
                if time.monotonic()>deadline:raise TimeoutError('ACQUISITION_DEADLINE')
                b=response.read(1<<20)
                if not b:break
                count+=len(b)
                if count>row['bytes']:raise Blocked('REMOTE_SIZE_EXCEEDED')
                h.update(b);out.write(b)
        out.flush();os.fsync(out.fileno())
    if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise Blocked('ASSET_SIZE_OR_SHA256_MISMATCH')
    os.link(partial,target,follow_symlinks=False)  # fails if another writer made target
    partial.unlink()  # only the exact exclusive partial created in this attempt
    return {'name':row['name'],'bytes':count,'sha256':h.hexdigest()}


def acquire(record,guard,write,opener=None):
    guard()  # TTY + regular host evidence, before directory creation/network
    d=manifest();target=safe_path(record['model_dir'],must_exist=False)
    if target.exists() or target.is_symlink():raise Blocked('FRESH_FIXED_MODEL_DIRECTORY_REQUIRED_NO_RETRY')
    ancestor=target.parent
    while not ancestor.exists():ancestor=ancestor.parent
    if shutil.disk_usage(ancestor).free<d['required_bytes']+(2<<30):raise Blocked('FIXED_WEIGHT_BYTES_PLUS_2GIB_FREE_REQUIRED')
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    target.mkdir(mode=0o700)
    report={'status':'ACQUIRING','repo':d['repo'],'revision':d['revision'],'required_bytes':d['required_bytes'],
            'files':[],'request_intents':[],'automatic_retry':False,'model_executions':0}
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirects())
    deadline=time.monotonic()+7200
    try:
        for r in d['required_files']:
            # Each intent is durable before network; interruption is never silently retried.
            intent=target/('intent-'+r['name']+'.json')
            write(intent,{'name':r['name'],'state':'REQUEST_INTENT_NO_RETRY'})
            report['request_intents'].append(r['name'])
            report['files'].append(fetch_one(r,target/r['name'],opener,deadline))
            intent.unlink()  # only owned intent, completed exact bytes/hash now exists
        report['status']='ACQUIRED_ALL20_SHA256_VERIFIED'
    except BaseException as exc:
        report.update(status='UNKNOWN_OR_FAILED_NO_RETRY',reason=type(exc).__name__)
        raise
    finally:write(target/'acquisition.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acquire-human-approved',action='store_true')
    p.add_argument('--operator-json',type=Path);p.add_argument('--operator-sha256')
    a=p.parse_args()
    if not a.acquire_human_approved:
        print(json.dumps({'status':'PREPARED_INDIVIDUAL_APPROVAL_REQUIRED','required_bytes':manifest()['required_bytes'],'model_executions':0}));return 0
    if not sys.stdin.isatty():raise Blocked('HUMAN_HOST_TERMINAL_REQUIRED')
    install_sigterm_handler()
    record=operator_record(a.operator_json,a.operator_sha256,purpose='acquire')
    Coordinator,_,write,_=helpers();coordinator=Coordinator(record['project_root'],record)
    # Only preflight takes the LLM lock. Downloading immutable data must not
    # block resident30B generation for the two-hour transfer bound.
    coordinator.guard()
    with coordinator.locked():
        coordinator.guard();coordinator.idle()
    result=acquire(record,coordinator.guard,write)
    print(json.dumps(result));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        # Never print exception URLs (redirects may contain ephemeral signed query strings).
        print(json.dumps({'status':'BLOCKED_OR_UNKNOWN_NO_RETRY','reason':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1)
