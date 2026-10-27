#!/usr/bin/env python3
"""One attempt per task; retain raw API responses and unmodified extracted code."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request

os.chdir(Path(__file__).resolve().parent.parent)
tasks_path=Path('evaluation/coder/tasks.json')
tasks=json.loads(tasks_path.read_text())
work=Path('logs/coder/eval')
work.mkdir(exist_ok=False)
summary={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'tasks_sha256':hashlib.sha256(tasks_path.read_bytes()).hexdigest(),
         'context':32768,'attempts_per_task':1,'results':{}}
for task in tasks:
    payload={'model':'kiss-qwen3-coder-30b',
             'messages':[{'role':'system','content':'Follow the stated specification and output format precisely. Do not invent unspecified requirements.'},
                         {'role':'user','content':task['prompt']}],
             'temperature':0,'seed':42,'max_tokens':2048,'stream':False,'cache_prompt':False}
    request=urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    start=time.monotonic()
    with urllib.request.urlopen(request,timeout=300) as response: result=json.load(response)
    record={'payload':payload,'response':result,'wall_seconds':time.monotonic()-start}
    with (work/(task['id']+'-response.json')).open('x') as output: json.dump(record,output,ensure_ascii=False,indent=2)
    text=result['choices'][0]['message']['content'].strip()
    status={'finish_reason':result['choices'][0]['finish_reason'],'timings':result['timings']}
    if task['kind']=='code':
        match=re.fullmatch(r'```[^\n]*\n(.*?)\n```',text,re.DOTALL)
        if match and text.count('```')==2:
            with (work/task['file']).open('x') as output: output.write(match.group(1)+'\n')
            status['format']='PASS'
        else: status.update(format='FAIL',reason='Expected exactly one fenced code block')
    else:
        try:
            status['parsed']=json.loads(text)
            status['format']='PASS'
        except json.JSONDecodeError as error: status.update(format='FAIL',reason=str(error))
        status['semantic_review']='pending independent review'
    summary['results'][task['id']]=status
    print(task['id'],status['format'],result['choices'][0]['finish_reason'],result['timings']['predicted_n'],flush=True)
with (work/'generation-summary.json').open('x') as output: json.dump(summary,output,ensure_ascii=False,indent=2)
