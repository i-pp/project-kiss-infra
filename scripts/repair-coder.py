#!/usr/bin/env python3
"""Seven fixed tasks, fresh generation, at most three repairs, independent gates."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'evaluation/coder/repair'))
from sandbox import execute, IMAGE
from feedback import feedback

MAX_REPAIRS = 3
BASE = 'http://127.0.0.1:8080'
MODEL = 'kiss-qwen3-coder-30b'


def save(path, data):
    with path.open('x') as output: json.dump(data,output,ensure_ascii=False,indent=2)


def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=180) as response: return json.load(response)


def fingerprint(cid):
    data = json.loads(subprocess.check_output(['docker','inspect',cid],text=True,timeout=30))[0]
    return {'id':data['Id'],'image':data['Image'],'started_at':data['State']['StartedAt'],
            'config_sha256':hashlib.sha256(json.dumps(data['Config'],sort_keys=True).encode()).hexdigest(),
            'host_config_sha256':hashlib.sha256(json.dumps(data['HostConfig'],sort_keys=True).encode()).hexdigest(),
            'health':data['State']['Health']['Status']}


def fixture_hashes():
    names = ['tasks.json','aapcs_check.S','arm_test.c','c_parse_test.cpp','cpp_alias_test.cpp',
             'guarded.h','posix_write_test.c','rust_prefix_test.rs']
    paths = [ROOT/'evaluation/coder'/name for name in names]
    paths += sorted((ROOT/'evaluation/coder/repair').glob('*.py'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    for path in ['logs/repair-isolation-exec.json','logs/repair-runner-controls.json']:
        assert json.loads((ROOT/path).read_text())['checks']=='PASS',path
    assert api('/health')['status']=='ok'
    props = api('/props')
    assert props['model_alias']==MODEL, props['model_alias']
    cid = subprocess.check_output(['sh','scripts/coder-compose.sh','ps','-q','llama-server'],
                                  cwd=ROOT,text=True,timeout=30).strip()
    before = fingerprint(cid)
    frozen = fixture_hashes()
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = ROOT/'logs/repair'/run_id
    destination.mkdir(parents=True,exist_ok=False)
    report = {'run_id':run_id,'model':MODEL,'context':props['default_generation_settings']['n_ctx'],
              'max_repairs':MAX_REPAIRS,'verifier_image':IMAGE,'server_before':before,
              'fixtures_sha256':frozen,'complete':False,'tasks':[]}
    save(destination/'manifest.json',report)
    tasks = [t for t in json.loads((ROOT/'evaluation/coder/tasks.json').read_text()) if t['kind']=='code']
    started = time.monotonic()
    try:
        for task in tasks:
            task_started = time.monotonic()
            messages = [{'role':'system','content':'Follow the stated specification and output format precisely. Do not invent unspecified requirements.'},
                        {'role':'user','content':task['prompt']}]
            history = []
            for number in range(MAX_REPAIRS+1):
                assert fixture_hashes()==frozen, 'Independent fixtures/runtime changed; abort'
                if time.monotonic()-started > 1800: raise RuntimeError('Overall 30-minute budget exceeded')
                attempt = destination/task['id']/f'attempt-{number}'
                attempt.mkdir(parents=True,exist_ok=False)
                attempt_started = time.monotonic()
                payload = {'model':MODEL,'messages':messages.copy(),'temperature':0,'seed':42,
                           'max_tokens':2048,'stream':False,'cache_prompt':False}
                api_started = time.monotonic()
                response = api('/v1/chat/completions',payload)
                api_seconds = time.monotonic()-api_started
                save(attempt/'api.json',{'payload':payload,'response':response,'wall_seconds':api_seconds})
                text = response['choices'][0]['message']['content'].strip()
                match = re.fullmatch(r'```[^\n]*\n(.*?)\n```',text,re.DOTALL)
                if not match or text.count('```')!=2 or response['choices'][0]['finish_reason']!='stop':
                    verdict = {'status':'FAIL','format_error':True,'steps':[]}
                    verification_seconds = 0
                else:
                    (attempt/task['file']).write_text(match.group(1)+'\n')
                    sandbox = execute(['python3','/suite/repair/runner.py',task['id']],candidate=attempt)
                    save(attempt/'sandbox.json',sandbox)
                    verification_seconds = sandbox['wall_seconds']
                    if sandbox['limit_reason'] or sandbox['state']['OOMKilled']:
                        verdict = {'status':'FAIL','limit_reason':sandbox['limit_reason'] or 'memory_limit','steps':[]}
                    else:
                        if sandbox['state']['ExitCode']!=0:
                            raise RuntimeError('Trusted runner failed; do not treat infrastructure failure as model failure: '+sandbox['output'][-2000:])
                        verdict = json.loads(sandbox['output'])
                        assert verdict['task']==task['id'] and verdict['status'] in ['PASS','FAIL']
                    save(attempt/'verification.json',verdict)
                assert fixture_hashes()==frozen, 'Independent fixtures/runtime changed; abort'
                usage = response['usage']
                assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
                entry = {'attempt':number,'status':verdict['status'],'usage':usage,
                         'api_seconds':api_seconds,'verification_seconds':verification_seconds,
                         'wall_seconds':time.monotonic()-attempt_started,'failure':verdict.get('failure')}
                if verdict['status']=='FAIL':
                    entry['feedback'] = feedback(verdict,task['file'])
                    (attempt/'feedback.txt').write_text(entry['feedback']+'\n')
                history.append(entry)
                save(attempt/'result.json',entry)
                print(task['id'],f'attempt={number}',verdict['status'],
                      f'tokens={usage["total_tokens"]}',flush=True)
                if verdict['status']=='PASS': break
                if number<MAX_REPAIRS:
                    messages += [{'role':'assistant','content':text},{'role':'user','content':entry['feedback']}]
            result = {'id':task['id'],'initial_status':history[0]['status'],
                      'repairs_used':history[-1]['attempt'],'final_status':history[-1]['status'],
                      'history':history,'wall_seconds':time.monotonic()-task_started,
                      'tokens':{key:sum(h['usage'][key] for h in history) for key in ['prompt_tokens','completion_tokens','total_tokens']},
                      'resolved_failures':[h['feedback'] for h in history[:-1] if h['status']=='FAIL'] if history[-1]['status']=='PASS' else [],
                      'remaining_problem':history[-1].get('feedback')}
            report['tasks'].append(result)
            save(destination/task['id']/'summary.json',result)
        report['complete'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        report['wall_seconds'] = time.monotonic()-started
        report['server_after'] = fingerprint(cid)
        report['server_unchanged'] = report['server_after']==before
        report['fixtures_unchanged'] = fixture_hashes()==frozen
        report['initial_passed'] = sum(t['initial_status']=='PASS' for t in report['tasks'])
        report['final_passed'] = sum(t['final_status']=='PASS' for t in report['tasks'])
        report['tokens'] = {k:sum(t['tokens'][k] for t in report['tasks']) for k in ['prompt_tokens','completion_tokens','total_tokens']}
        save(destination/'report.json',report)
        print('Report:',destination/'report.json',flush=True)
        assert report['server_unchanged'] and report['fixtures_unchanged']


if __name__=='__main__': main()
