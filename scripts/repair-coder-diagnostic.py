#!/usr/bin/env python3
# KISS Open License Version 1.0 (KOL-v1)
#
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1
#
# Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
# Contributors may add copyright notices for their own original modifications.
# Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
#
# Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
# without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
#
# Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
# KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
#
# This header is a summary, not a separate license or an amendment to KOL-v1.
# All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

"""Paired diagnostic experiment; historical baseline and its code stay unchanged."""
import datetime
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('repair_baseline',ROOT/'scripts/repair-coder.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
sys.path.insert(0,str(ROOT/'evaluation/coder/diagnostic'))
from diagnosis import diagnosis_payload, parse_diagnosis, repair_message
from assessment import assess

OLD = ROOT/'logs/repair/20261027T084214958944Z'
TOKEN_KEYS = ['prompt_tokens','completion_tokens','total_tokens']


def hashes(paths):
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def source_from_response(response):
    text = response['choices'][0]['message']['content'].strip()
    match = re.fullmatch(r'```[^\n]*\n(.*?)\n```',text,re.DOTALL)
    if not match or text.count('```')!=2 or response['choices'][0]['finish_reason']!='stop':
        return text,None
    return text,match.group(1)+'\n'


def add_usage(records):
    return {k:sum(r[k] for r in records) for k in TOKEN_KEYS}


def call(payload,path):
    started = time.monotonic()
    response = baseline.api('/v1/chat/completions',payload)
    seconds = time.monotonic()-started
    baseline.save(path,{'payload':payload,'response':response,'wall_seconds':seconds})
    usage = response['usage']
    if usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']:
        raise RuntimeError('Inconsistent API token accounting')
    if response['timings']['cache_n']!=0: raise RuntimeError('Unexpected prompt-cache reuse')
    return response,seconds


def verify(task,code,path):
    if code is None:
        verdict = {'status':'FAIL','format_error':True,'steps':[]}
        baseline.save(path/'verification.json',verdict)
        return verdict,0
    with (path/task['file']).open('x') as output: output.write(code)
    sandbox = baseline.execute(['python3','/suite/repair/runner.py',task['id']],candidate=path)
    baseline.save(path/'sandbox.json',sandbox)
    if sandbox['limit_reason'] or sandbox['state']['OOMKilled']:
        verdict = {'status':'FAIL','limit_reason':sandbox['limit_reason'] or 'memory_limit','steps':[]}
    else:
        if sandbox['state']['ExitCode']!=0:
            raise RuntimeError('Trusted verifier failed; experiment stopped: '+sandbox['output'][-1500:])
        verdict = json.loads(sandbox['output'])
        if verdict['task']!=task['id'] or verdict['status'] not in ['PASS','FAIL']:
            raise RuntimeError('Invalid trusted verifier result')
    baseline.save(path/'verification.json',verdict)
    return verdict,sandbox['wall_seconds']


def main():
    old = json.loads((OLD/'report.json').read_text())
    frozen_old = hashes([p for p in OLD.rglob('*') if p.is_file()])
    frozen = baseline.fixture_hashes()
    if frozen!=old['fixtures_sha256']: raise RuntimeError('Baseline fixtures/runtime no longer match')
    protected = hashes([ROOT/'scripts/repair-coder.py',ROOT/'compose.yaml',ROOT/'scripts/coder-compose.sh'])
    implementation = hashes([Path(__file__),*(ROOT/'evaluation/coder/diagnostic').glob('*.py')])
    for name in ['repair-isolation-exec.json','repair-runner-controls.json']:
        if json.loads((ROOT/'logs'/name).read_text())['checks']!='PASS': raise RuntimeError('Isolation precondition missing')
    props = baseline.api('/props')
    if props['model_alias']!=baseline.MODEL or props['default_generation_settings']['n_ctx']!=old['context']:
        raise RuntimeError('Model/context comparison condition changed')
    cid = subprocess.check_output(['sh','scripts/coder-compose.sh','ps','-q','llama-server'],cwd=ROOT,text=True).strip()
    before = baseline.fingerprint(cid)
    if before!=old['server_after']: raise RuntimeError('Server configuration/start state differs from baseline')
    image = json.loads(subprocess.check_output(['docker','image','inspect',baseline.IMAGE],text=True))[0]
    if image['Id']!=old['verifier_image']: raise RuntimeError('Verifier image differs from baseline')
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = ROOT/'logs/repair-v2'/run_id
    destination.mkdir(parents=True,exist_ok=False)
    report = {'run_id':run_id,'mode':'diagnostic','historical_baseline':str(OLD.relative_to(ROOT)),
              'paired_initial_candidates':True,'initial_generation_reexecuted':False,
              'context':old['context'],'model':baseline.MODEL,'max_repairs':3,
              'generator_settings':{'temperature':0,'seed':42,'max_tokens':2048,'stream':False,'cache_prompt':False},
              'diagnostic_settings':{'temperature':0,'seed':42,'max_tokens':1024,'stream':False,'cache_prompt':False},
              'server_before':before,'fixtures_sha256':frozen,'baseline_log_sha256':frozen_old,
              'protected_files_sha256':protected,'implementation_sha256':implementation,
              'complete':False,'replays':[],'tasks':[]}
    baseline.save(destination/'manifest.json',report)
    tasks = [t for t in json.loads((ROOT/'evaluation/coder/tasks.json').read_text()) if t['kind']=='code']
    old_tasks = {t['id']:t for t in old['tasks']}
    started = time.monotonic()

    def unchanged():
        if baseline.fixture_hashes()!=frozen or hashes([ROOT/n for n in protected])!=protected:
            raise RuntimeError('Protected fixture, runtime or baseline script changed')
        if hashes([ROOT/n for n in implementation])!=implementation:
            raise RuntimeError('Diagnostic implementation changed during experiment')
        if hashes([p for p in OLD.rglob('*') if p.is_file()])!=frozen_old:
            raise RuntimeError('Historical baseline logs changed')
        if baseline.fingerprint(cid)!=before:
            raise RuntimeError('Server settings/start state changed; comparison stopped')

    try:
        # All seven starts must reproduce before ANY diagnostic/generator call.
        inputs = {}
        transitions = []
        for task in tasks:
            unchanged()
            historical = json.loads((OLD/task['id']/'attempt-0/api.json').read_text())
            text,code = source_from_response(historical['response'])
            if code is None or code!=(OLD/task['id']/'attempt-0'/task['file']).read_text():
                raise RuntimeError('Historical initial candidate does not match its response')
            path = destination/task['id']/'attempt-0'
            path.mkdir(parents=True,exist_ok=False)
            replay_started = time.monotonic()
            verdict,verification_seconds = verify(task,code,path)
            elapsed = time.monotonic()-replay_started
            if verdict['status']!=old_tasks[task['id']]['initial_status']:
                raise RuntimeError('Initial candidate verdict not reproducible: '+task['id'])
            entry = {'task':task['id'],'status':verdict['status'],'verification_seconds':verification_seconds,
                     'wall_seconds':elapsed,'historical_api_usage':historical['response']['usage'],
                     'historical_api_seconds':historical['wall_seconds'],'actual_api_calls':0,
                     'historical_api_path':str((OLD/task['id']/'attempt-0/api.json').relative_to(ROOT))}
            baseline.save(path/'replay.json',entry)
            report['replays'].append(entry)
            inputs[task['id']] = (historical,text,code,verdict)
            previous = None
            for h in old_tasks[task['id']]['history']:
                d = OLD/task['id']/f"attempt-{h['attempt']}"
                s = (d/task['file']).read_text()
                v = json.loads((d/'verification.json').read_text())
                transitions.append({'task':task['id'],'attempt':h['attempt'],'status':v['status'],
                                    'failure':v.get('failure'),'source_sha256':hashlib.sha256(s.encode()).hexdigest(),
                                    'same_as_previous':previous==s if previous is not None else None,
                                    'diff':None if previous is None else ''.join(difflib.unified_diff(previous.splitlines(True),s.splitlines(True))),
                                    'evidence_file':str((d/'verification.json').relative_to(ROOT))})
                previous = s
            print(task['id'],'initial replay',verdict['status'],flush=True)
        baseline.save(destination/'baseline-transitions.json',transitions)
        report['all_initial_candidates_reproduced'] = True
        unchanged()

        for task in tasks:
            historical,text,code,verdict = inputs[task['id']]
            original_verdict = verdict
            task_started = time.monotonic()
            messages = historical['payload']['messages'].copy()
            history = []
            for number in range(1,4):
                if verdict['status']=='PASS': break
                unchanged()
                if time.monotonic()-started>1800: raise RuntimeError('Overall budget exceeded')
                path = destination/task['id']/f'attempt-{number}'
                path.mkdir(parents=True,exist_ok=False)
                revision_started = time.monotonic()
                filtered = baseline.feedback(verdict,task['file'])
                (path/'filtered-feedback.txt').write_text(filtered+'\n')
                # The ONLY model-facing diagnostic inputs come from these three
                # values. No Phase A report, raw verifier or post-assessment.
                payload = diagnosis_payload(task['prompt'],code or text,filtered,baseline.MODEL)
                response,diagnosis_seconds = call(payload,path/'diagnosis-api.json')
                if response['choices'][0]['finish_reason']!='stop': raise RuntimeError('Diagnosis truncated; stop rather than change comparison')
                diagnosis = parse_diagnosis(response['choices'][0]['message']['content'])
                baseline.save(path/'diagnosis.json',diagnosis)
                repair = repair_message(filtered,diagnosis)
                messages += [{'role':'assistant','content':text},{'role':'user','content':repair}]
                generator_payload = {'model':baseline.MODEL,'messages':messages.copy(),
                                     **report['generator_settings']}
                generated,generator_seconds = call(generator_payload,path/'generator-api.json')
                new_text,new_code = source_from_response(generated)
                new_verdict,verification_seconds = verify(task,new_code,path)
                assessment = assess(code or '',new_code or '',verdict,new_verdict,diagnosis)
                baseline.save(path/'post-assessment.json',assessment)
                record = {'repair':number,'diagnosis_hypotheses':diagnosis['hypotheses'],
                          'repair_plan':diagnosis['repair_plan'],'actual_code_diff':assessment['code_diff'],
                          'before_status':verdict['status'],'status':new_verdict['status'],
                          'independent_result_file':'verification.json','post_assessment':assessment,
                          'diagnosis_usage':response['usage'],'generator_usage':generated['usage'],
                          'diagnosis_seconds':diagnosis_seconds,'generator_seconds':generator_seconds,
                          'verification_seconds':verification_seconds,'wall_seconds':time.monotonic()-revision_started}
                baseline.save(path/'revision.json',record)
                history.append(record)
                text,code,verdict = new_text,new_code,new_verdict
                unchanged()
                print(task['id'],f'repair={number}',verdict['status'],
                      f'diagnosis_tokens={response["usage"]["total_tokens"]}',flush=True)
            replay = next(x for x in report['replays'] if x['task']==task['id'])
            diagnosis_usage = add_usage([h['diagnosis_usage'] for h in history])
            generator_usage = add_usage([h['generator_usage'] for h in history])
            actual_usage = {k:diagnosis_usage[k]+generator_usage[k] for k in TOKEN_KEYS}
            result = {'id':task['id'],'initial_status':original_verdict['status'],'repairs_used':len(history),
                      'final_status':verdict['status'],'history':history,
                      'diagnosis_usage':diagnosis_usage,'generator_repair_usage':generator_usage,
                      'actual_api_usage':actual_usage,
                      'reused_initial_api_usage':replay['historical_api_usage'],
                      'normalized_api_usage':{k:actual_usage[k]+replay['historical_api_usage'][k] for k in TOKEN_KEYS},
                      'diagnosis_seconds':sum(h['diagnosis_seconds'] for h in history),
                      'actual_wall_seconds':time.monotonic()-task_started+replay['wall_seconds']}
            result['normalized_wall_seconds'] = result['actual_wall_seconds']+replay['historical_api_seconds']
            baseline.save(destination/task['id']/'summary.json',result)
            report['tasks'].append(result)
        unchanged()
        report['complete'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        report['actual_wall_seconds'] = time.monotonic()-started
        report['server_after'] = baseline.fingerprint(cid)
        report['server_unchanged'] = report['server_after']==before
        report['fixtures_unchanged'] = baseline.fixture_hashes()==frozen
        report['baseline_logs_unchanged'] = hashes([p for p in OLD.rglob('*') if p.is_file()])==frozen_old
        report['initial_passed'] = sum(t['initial_status']=='PASS' for t in report['tasks'])
        report['final_passed'] = sum(t['final_status']=='PASS' for t in report['tasks'])
        for field in ['diagnosis_usage','generator_repair_usage','actual_api_usage','reused_initial_api_usage','normalized_api_usage']:
            report[field] = add_usage([t[field] for t in report['tasks']])
        report['diagnosis_seconds'] = sum(t['diagnosis_seconds'] for t in report['tasks'])
        report['normalized_wall_seconds'] = report['actual_wall_seconds']+sum(x['historical_api_seconds'] for x in report['replays'])
        report['comparison'] = {'baseline_initial_passed':old['initial_passed'],'baseline_final_passed':old['final_passed'],
                                'baseline_usage':old['tokens'],'baseline_wall_seconds':old['wall_seconds'],
                                'caution':'Historical baseline, paired identical initial candidates; latency is not a simultaneous controlled measurement. Seven tasks do not support generalization.'}
        baseline.save(destination/'report.json',report)
        print('Report:',destination/'report.json',flush=True)
        if not (report['server_unchanged'] and report['fixtures_unchanged'] and report['baseline_logs_unchanged']):
            raise RuntimeError('Protected state changed')


if __name__=='__main__': main()
