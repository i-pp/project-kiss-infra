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

"""Benchmark fixed short input and a context-sized input, preserving Phase 2."""
import argparse
import datetime
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import urllib.request

os.chdir(Path(__file__).resolve().parent.parent)
parser=argparse.ArgumentParser()
parser.add_argument('context',type=int,choices=[8192,16384,32768])
args=parser.parse_args()
destination=Path(f'logs/coder/context-{args.context}.json')
if destination.exists(): raise SystemExit(f'Preserve existing {destination} before rerunning')
base='http://127.0.0.1:8080'

def api(path,payload=None,timeout=300):
    data=None if payload is None else json.dumps(payload).encode()
    request=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as response: return json.load(response)

props=api('/props')
assert props['default_generation_settings']['n_ctx']==args.context, props
cid=subprocess.check_output(['sh','scripts/coder-compose.sh','ps','-q','llama-server'],text=True).strip()
pid=subprocess.check_output(['docker','inspect','--format','{{.State.Pid}}',cid],text=True).strip()
cg=next(s[3:] for s in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if s.startswith('0::'))
cg=Path('/sys/fs/cgroup')/cg.lstrip('/')
device=Path('/sys/class/drm/renderD128/device')

def snapshot():
    return {'monotonic':time.monotonic(),
            'vram_bytes':int((device/'mem_info_vram_used').read_text()),
            'gtt_bytes':int((device/'mem_info_gtt_used').read_text()),
            'ram_bytes':int((cg/'memory.current').read_text()),
            'ram_peak_bytes':int((cg/'memory.peak').read_text())}

short='Explain how a local language model processes a prompt and generates text. Describe tokenization, prompt processing, the KV cache, GPU offloading, and autoregressive decoding in order. Write at least 300 words.'
settings={'model':'kiss-qwen3-coder-30b','temperature':0,'seed':42,'max_tokens':128,'stream':False,'cache_prompt':False}

def chat(prompt):
    start=time.monotonic()
    result=api('/v1/chat/completions',{**settings,'messages':[{'role':'user','content':prompt}]})
    assert result['choices'][0]['message']['content'].strip(),result
    assert result['timings']['cache_n']==0,result['timings']
    return {'wall_seconds':time.monotonic()-start,'response':result}

def long_prompt():
    # Exact chat-template token counting before submitting the large request.
    def make(n):
        return ('Read this synthetic C source and explain integer and memory safety considerations. Write at least 300 words.\n```c\n'
                +'\n'.join(f'uint32_t f_{i}(uint32_t a, uint32_t b) {{ return (a ^ b) + {i}U; }}' for i in range(n))
                +'\n```\nGive your review now.')
    def count(prompt):
        formatted=api('/apply-template',{'messages':[{'role':'user','content':prompt}],'add_generation_prompt':True})['prompt']
        return len(api('/tokenize',{'content':formatted,'add_special':False})['tokens'])
    low,high=0,args.context//8
    while low<high:
        middle=(low+high+1)//2
        if count(make(middle))<=args.context-1024: low=middle
        else: high=middle-1
    prompt=make(low)
    return prompt,count(prompt)

report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'context':args.context,'settings':settings,'short_prompt':short,'props':props,'idle':snapshot()}
report['warmup']=chat(short)
samples=[];errors=[];stop=threading.Event();phase='short'
def monitor():
    while not stop.is_set():
        try: samples.append({**snapshot(),'phase':phase})
        except Exception as error: errors.append(str(error));return
        stop.wait(0.1)
worker=threading.Thread(target=monitor);worker.start()
try:
    report['short_runs']=[chat(short) for _ in range(3)]
    phase='prepare_long'
    prompt,count=long_prompt()
    report['long_prompt']=prompt;report['long_prompt_tokens_preflight']=count
    phase='long'
    report['long_run']=chat(prompt)
finally:
    stop.set();worker.join()
if errors: raise RuntimeError(errors)
report['after']=snapshot();report['samples']=samples
report['summary']={
    'short_prompt_tps_median':statistics.median(r['response']['timings']['prompt_per_second'] for r in report['short_runs']),
    'short_generation_tps_median':statistics.median(r['response']['timings']['predicted_per_second'] for r in report['short_runs']),
    'short_prompt_tokens':[r['response']['timings']['prompt_n'] for r in report['short_runs']],
    'short_generation_tokens':[r['response']['timings']['predicted_n'] for r in report['short_runs']],
    'long_timings':report['long_run']['response']['timings'],
    'sampled_max_vram_bytes':max(s['vram_bytes'] for s in samples),
    'sampled_max_gtt_bytes':max(s['gtt_bytes'] for s in samples),
    'sampled_max_ram_bytes':max(s['ram_bytes'] for s in samples),
    'cgroup_lifetime_peak_ram_bytes':report['after']['ram_peak_bytes'],
    'samples':len(samples)}
destination.parent.mkdir(parents=True,exist_ok=True)
with destination.open('x') as output: json.dump(report,output,ensure_ascii=False,indent=2)
print(json.dumps(report['summary'],indent=2),flush=True)
if report['summary']['sampled_max_vram_bytes']>48*1024**3:
    raise SystemExit('Observed GPU usage exceeded 48GiB; stop context expansion and investigate')
