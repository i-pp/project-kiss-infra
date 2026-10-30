"""Normal-host fixed-image CPU source read; no backend import or GPU device."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import uuid

import inspect_sglang_content_host as base

from read_loader_static import FILES as EXPECTED_FILES



def validate(data):
    if (not isinstance(data,dict) or data.get('status')!='STATIC_SOURCE_ONLY_NO_BACKEND_IMPORT'
            or any(type(data.get(k)) is not int or data[k]!=0 for k in ('source_executions','gpu_operations','generation_requests'))
            or set(data.get('files',{}))!=set(EXPECTED_FILES)):
        raise ValueError('FIXED_STATIC_SOURCE_SCHEMA')
    for row in data['files'].values():
        if not isinstance(row,dict) or row.get('status') not in ('READ','UNAVAILABLE'):
            raise ValueError('STATIC_SOURCE_ROW_SCHEMA')
        if row.get('status')=='READ' and (row.get('source_executed') is not False
                or not isinstance(row.get('sha256'),str) or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None
                or type(row.get('bytes')) is not int or not 0<=row['bytes']<=512*1024
                or not isinstance(row.get('functions_as_data'),dict)):
            raise ValueError('STATIC_SOURCE_RESULT_CHANGED')
    return data


def capture_once():
    signal.signal(signal.SIGTERM,base.terminate)
    repo,guard,private_dir,write=base.installed_guard();guard()
    root=private_dir(repo/'agents/local_llm/.runtime/backend-runtime/loader-source-inspection')
    if (root/'UNCERTAIN.json').exists():raise RuntimeError('PRIOR_CPU_INSPECTION_UNKNOWN_NO_RETRY')
    if any((p/'intent.json').exists() and not (p/'receipt.json').exists() for p in root.glob('run-*')):
        raise RuntimeError('PRIOR_CPU_INTENT_WITHOUT_TERMINAL_RECEIPT')
    payload_path=Path(__file__).with_name('read_loader_static.py');payload=payload_path.read_text()
    token=uuid.uuid4().hex;cmd=base.commands(os.getuid(),os.getgid(),token);name='aceis-sglang-content-'+token
    outdir=private_dir(root/('run-'+token));report={'status':'STARTING','owned_container_name':name,
        'image':base.IMAGE,'source_probe_sha256':hashlib.sha256(payload.encode()).hexdigest(),
        'container_run_intents':0,'generation_requests':0,'gpu_device_access':False,'automatic_retry':False}
    sys.path.insert(0,str(repo/'agents/local_llm'))
    from local_llm import Client
    try:
        with Client(runtime=repo/'agents/local_llm/.runtime').locked():
            code,stdout,stderr=base.invoke(cmd[0],None,15,guard)
            if code:
                write(outdir/'image-read-error.json',{'exit_code':code,'stderr':stderr[:4096],'untrusted_data':True})
                raise RuntimeError('FIXED_DOCKER_IMAGE_READ_UNAVAILABLE')
            report['identity']=base.verify_image(json.loads(stdout))
            write(outdir/'intent.json',{'purpose':'FIXED_LOADER_SOURCE_AS_DATA_ONLY','owned_container_name':name})
            report['container_run_intents']=1
            code,stdout,stderr=base.invoke(cmd[1],payload,30,guard)
            write(outdir/'cpu-output.json',{'exit_code':code,'stdout':stdout,'stderr':stderr,'untrusted_data':True})
            if code:raise RuntimeError('CPU_STATIC_READER_FAILED')
            data=validate(json.loads(stdout));report['result']=data
            absent=cmd[0][:3]+['container','ls','-a','--no-trunc','--filter','name=^/'+name+'$','--format','{{.ID}}']
            code,stdout,stderr=base.invoke(absent,None,10,guard)
            if code or stdout.strip():raise RuntimeError('CPU_CONTAINER_ABSENCE_NOT_CONFIRMED')
            report['cpu_container_absence_confirmed']=True
            report['status']='STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS'
            write(outdir/'receipt.json',report)
            print(json.dumps({'status':report['status'],'receipt':str(outdir/'receipt.json'),
                'source_read_status':{k:v['status'] for k,v in data['files'].items()},
                'generation_requests':0,'model_lifecycle_requests':0,'gpu_device_access':False}));return outdir/'receipt.json'
    except BaseException as exc:
        report.update(status='UNKNOWN_CPU_INSPECTION_NO_RETRY' if report['container_run_intents'] else 'BLOCKED_BEFORE_CPU_RUN',
            reason=type(exc).__name__+':'+str(exc)[:192])
        if report['container_run_intents']:write(root/'UNCERTAIN.json',{'receipt':str(outdir/'receipt.json'),'owned_container_name':name})
        write(outdir/'receipt.json',report)
        print(json.dumps({'status':report['status'],'reason':report['reason'],'receipt':str(outdir/'receipt.json'),
            'instruction':'Read audit; do not retry or start a model while CPU outcome is unknown.'}));raise RuntimeError(report['status']) from exc


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inspect-human',action='store_true');a=p.parse_args()
    if not a.inspect_human:
        print(json.dumps({'status':'PREPARED_STATIC_SOURCE_READ_ONLY','generation_requests':0,'container_runs':0}));return 0
    try:capture_once();return 0
    except RuntimeError:return 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_RETRY','reason':type(exc).__name__+':'+str(exc)[:192]}),file=sys.stderr)
        raise SystemExit(1)
