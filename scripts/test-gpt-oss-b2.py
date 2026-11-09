#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Bounded single-model B2 experiment; existing services and tests are read-only."""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'evaluation/coder/repair'))
from sandbox import execute, IMAGE
from feedback import feedback

LOCK = json.loads((ROOT/'inference/gpt-oss-b2/versions.lock.json').read_text())
PROJECT = 'project-kiss-gpt-oss-b2'
MODEL = 'kiss-gpt-oss-20b-mxfp4'
OLD = 'project-kiss-phase2-llama-server-1'
B1 = 'project-kiss-vllm-b1-server-1'
GIB = 1024**3


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def shell(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=30)


def inspect(cid):
    return json.loads(shell('docker', 'inspect', cid))[0]


def fingerprint(name):
    c = inspect(name)
    return {k: c[k] for k in ['Id', 'Image', 'Config', 'HostConfig', 'RestartCount']} | {
        'started_at': c['State']['StartedAt'], 'running': c['State']['Running'],
        'health': c['State'].get('Health', {}).get('Status')}


def compose(*args):
    return ['sh', str(ROOT/'scripts/gpt-oss-compose.sh'), *args]


def api(path, body=None, port=8082, timeout=180):
    start = time.monotonic()
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(2*1024*1024+1)
        assert len(raw) <= 2*1024*1024, 'API response limit'
        return {'http_status': response.status, 'body': json.loads(raw) if raw else None,
                'seconds': time.monotonic()-start}


def resource_sample():
    return {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'linux': {l.split(':')[0]: int(l.split()[1])*1024
                  for l in Path('/proc/meminfo').read_text().splitlines()
                  if l.split(':')[0] in ['MemAvailable', 'MemTotal', 'SwapFree']},
        'gpu': {p.name: int(p.read_text()) for p in Path('/sys/class/drm/card1/device').glob('mem_info_*')
                if p.name in ['mem_info_vram_used', 'mem_info_vram_total', 'mem_info_gtt_used', 'mem_info_gtt_total']}}


def resource_reason(s, preflight=False):
    available = s['linux']['MemAvailable']
    if preflight:
        free = s['gpu']['mem_info_vram_total']-s['gpu']['mem_info_vram_used']
        if min(free, available) < 24*GIB:
            return 'Preflight GPU free or Linux MemAvailable below 24 GiB'
    elif available < 8*GIB:
        return 'EMERGENCY Linux MemAvailable below 8 GiB'
    elif available < 16*GIB or s['gpu']['mem_info_vram_used'] > 58*GIB:
        return 'Sustained-threshold GPU/RAM pressure'
    return None


def stop_owned(cid):
    if not cid:
        return
    c = inspect(cid)
    assert c['Config'].get('Labels', {}).get('com.docker.compose.project') == PROJECT
    assert c['Config']['User'].split(':')[0] != '0'
    if c['State']['Running']:
        subprocess.run(['docker', 'stop', '-t', '10', cid], timeout=30, check=True,
                       stdout=subprocess.DEVNULL)


class Guard:
    def __init__(self, directory):
        self.directory = directory
        self.before = {n: fingerprint(n) for n in [OLD, B1]}
        assert self.before[OLD]['health'] == 'healthy' and self.before[OLD]['running']
        assert not self.before[B1]['running'], 'Preserve B1 state; do not stop it'
        reason = resource_reason(resource_sample(), True)
        if reason:
            raise RuntimeError(reason)
        self.cid = None
        self.phase = 'preflight'
        self.failure = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.cursor = shell('journalctl', '-k', '-n', '0', '--show-cursor', '--no-pager').split('-- cursor: ', 1)[1].strip()

    def check(self):
        if self.failure:
            raise RuntimeError(self.failure)

    def start(self):
        self.thread.start()

    def watch(self):
        low_since = None
        try:
            with (self.directory/'memory.jsonl').open('x') as f:
                while not self.done.is_set():
                    s = resource_sample(); s['phase'] = self.phase
                    for name, expected in self.before.items():
                        if fingerprint(name) != expected:
                            raise RuntimeError('Protected service state changed: '+name)
                    assert api('/health', port=8080, timeout=5)['body']['status'] == 'ok'
                    messages = shell('journalctl', '-k', '--after-cursor', self.cursor,
                                     '--show-cursor', '--no-pager', '-o', 'json')
                    for line in messages.splitlines():
                        if line.startswith('-- cursor: '):
                            self.cursor = line.split('-- cursor: ', 1)[1]
                        elif line.startswith('{'):
                            msg = json.loads(line).get('MESSAGE', '')
                            if re.search(r'amdgpu.*(GPU reset|GPU fault|ring .*timeout|VM_L2_PROTECTION)|Out of memory: Killed process', msg, re.I):
                                raise RuntimeError('Kernel fault: '+msg)
                    if self.cid:
                        c = inspect(self.cid)
                        s['state'] = {k: c['State'][k] for k in ['Running', 'Pid', 'OOMKilled', 'StartedAt']}
                        assert not c['State']['OOMKilled'], 'B2 OOMKilled'
                        pid = c['State']['Pid']
                        if pid:
                            try:
                                cg = Path(f'/proc/{pid}/cgroup').read_text().split('0::')[-1].strip()
                                base = Path('/sys/fs/cgroup')/cg.lstrip('/')
                                s['cgroup'] = {k: (base/k).read_text().strip() for k in
                                    ['memory.current', 'memory.peak', 'memory.events', 'cpu.max', 'pids.current']}
                                if any(int(l.split()[1]) for l in s['cgroup']['memory.events'].splitlines()
                                       if l.split()[0] in ['oom', 'oom_kill']):
                                    raise RuntimeError('B2 cgroup OOM event')
                            except FileNotFoundError:
                                # A normal owned-container restart can remove the old PID/cgroup.
                                s['cgroup_transition'] = True
                    f.write(json.dumps(s)+'\n'); f.flush()
                    reason = resource_reason(s)
                    if reason:
                        low_since = low_since or time.monotonic()
                        if reason.startswith('EMERGENCY') or time.monotonic()-low_since >= 6:
                            raise RuntimeError(reason)
                    else:
                        low_since = None
                    self.done.wait(1)
        except Exception as e:
            self.failure = str(e)
            save(self.directory/'safety-stop.json', {'reason': self.failure})
            stop_owned(self.cid)

    def finish(self):
        self.done.set(); self.thread.join(timeout=35)
        assert not self.thread.is_alive()
        self.check()


def old_probe():
    return api('/v1/chat/completions', {'model': 'kiss-qwen3-coder-30b',
        'messages': [{'role': 'user', 'content': 'Return only the integer result of 17 + 25.'}],
        'temperature': 0, 'max_tokens': 16}, port=8080, timeout=60)


def runtime_security(cid):
    c = inspect(cid); h = c['HostConfig']; pid = c['State']['Pid']
    assert c['Config']['User'].split(':')[0] != '0'
    assert not h['Privileged'] and h['ReadonlyRootfs'] and h['NetworkMode'] != 'host'
    assert h['CapDrop'] == ['ALL'] and not h['CapAdd']
    assert 'no-new-privileges:true' in h['SecurityOpt'] or 'no-new-privileges' in h['SecurityOpt']
    assert h['Memory'] == 24*GIB and h['MemorySwap'] == 24*GIB
    assert h['PidsLimit'] == 512 and h['NanoCpus'] == 8_000_000_000
    assert c['NetworkSettings']['Ports']['8080/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '8082'}]
    assert all(not m['RW'] for m in c['Mounts'] if m['Destination'] == '/model')
    status = {l.split(':')[0]: l.split(':', 1)[1].strip()
              for l in Path(f'/proc/{pid}/status').read_text().splitlines()
              if l.split(':')[0] in ['Uid', 'Gid', 'Groups', 'CapEff', 'NoNewPrivs', 'Seccomp']}
    assert status['Uid'].split()[1] != '0' and status['CapEff'] == '0000000000000000'
    assert status['NoNewPrivs'] == '1' and status['Seccomp'] == '2'
    return {'status': 'PASS', 'proc': status,
            'apparmor': Path(f'/proc/{pid}/attr/current').read_text().strip(), 'container': c}


def fixtures():
    paths = sorted(p for p in (ROOT/'evaluation/coder').rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def wait_ready(guard):
    start = time.monotonic()
    while time.monotonic()-start < 300:
        guard.check()
        if not inspect(guard.cid)['State']['Running']:
            raise RuntimeError('B2 server exited before readiness')
        try:
            result = api('/health', timeout=2)
            if result['http_status'] == 200:
                return time.monotonic()-start
        except Exception:
            guard.done.wait(1)
    raise TimeoutError('Readiness timeout (300s)')


def content(response):
    return response['choices'][0]['message'].get('content') or ''


def chat(messages, limit=2048):
    payload = {'model': MODEL, 'messages': messages, 'temperature': 0, 'seed': 42,
        'max_tokens': limit, 'stream': False, 'cache_prompt': False}
    return payload, api('/v1/chat/completions', payload)


def bench(messages):
    # Render using the server's real Harmony template/default reasoning settings.
    rendered = api('/apply-template', {'messages': messages})['body']['prompt']
    assert 'Reasoning: low' in rendered and '<|start|>' in rendered
    token_count = len(api('/tokenize', {'content': rendered, 'add_special': False})['body']['tokens'])
    request = {'prompt': rendered, 'n_predict': 256, 'temperature': 0, 'seed': 42,
               'cache_prompt': False, 'stream': True}
    req = urllib.request.Request('http://127.0.0.1:8082/completion',
        data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
    chunks = []; start = time.monotonic(); first = None
    with urllib.request.urlopen(req, timeout=180) as r:
        for line in r:
            if not line.startswith(b'data: ') or line.strip() == b'data: [DONE]':
                continue
            item = json.loads(line[6:]); chunks.append(item)
            if item.get('content') and first is None:
                first = time.monotonic()
    final = chunks[-1]
    assert final.get('timings', {}).get('predicted_n', 0) > 0
    return {'messages': messages, 'rendered_prompt': rendered, 'client_prompt_tokens': token_count,
            'request': request, 'chunks': chunks, 'timings': final['timings'],
            'ttft_seconds': None if first is None else first-start, 'wall_seconds': time.monotonic()-start,
            'note': 'Speed covers all generated tokens, including reasoning/control tokens; not code-only tokens.'}


def fixed_prompt():
    count = 400
    for _ in range(10):
        messages = [{'role': 'user', 'content': 'Read these inert markers, then write a short C unsigned sum function.\n'+' x'*count}]
        prompt = api('/apply-template', {'messages': messages})['body']['prompt']
        n = len(api('/tokenize', {'content': prompt, 'add_special': False})['body']['tokens'])
        if n == 512:
            return messages
        count += 512-n
        assert count > 0
    raise RuntimeError('Could not build the fixed 512-token Harmony prompt')


def verify(task, directory, response):
    text = content(response).strip()
    match = re.fullmatch(r'```[^\n]*\n(.*?)\n```', text, re.S)
    if response['choices'][0]['finish_reason'] != 'stop' or not match or text.count('```') != 2:
        verdict = {'status': 'FAIL', 'format_error': True, 'failure': 'truncation_or_final_format', 'steps': []}
    else:
        with (directory/task['file']).open('x') as f:
            f.write(match.group(1)+'\n')
        box = execute(['python3', '/suite/repair/runner.py', task['id']], candidate=directory)
        save(directory/'sandbox.json', box)
        if box['limit_reason'] or box['state']['OOMKilled']:
            verdict = {'status': 'FAIL', 'limit_reason': box['limit_reason'] or 'memory_limit', 'steps': []}
        elif box['state']['ExitCode']:
            raise RuntimeError('Trusted independent runner failed: '+box['output'][-1000:])
        else:
            verdict = json.loads(box['output'])
            assert verdict['task'] == task['id']
    save(directory/'verification.json', verdict)
    return verdict


def quality(directory, guard, frozen):
    tasks = [t for t in json.loads((ROOT/'evaluation/coder/tasks.json').read_text()) if t['kind'] == 'code']
    results = []
    for task in tasks:
        guard.check(); assert fixtures() == frozen
        base = [{'role': 'system', 'content': 'Follow the stated specification and output format precisely. Do not invent unspecified requirements.'},
                {'role': 'user', 'content': task['prompt']}]
        messages = base.copy(); history = []; previous = ''
        for number in range(LOCK['max_repairs']+1):
            dest = directory/task['id']/f'attempt-{number}'; dest.mkdir(parents=True)
            payload, response = chat(messages)
            save(dest/'api.json', {'payload': payload, **response})
            verdict = verify(task, dest, response['body'])
            guard.check(); assert fixtures() == frozen
            text = content(response['body'])
            entry = {'attempt': number, 'status': verdict['status'], 'failure': verdict.get('failure'),
                     'usage': response['body'].get('usage'), 'api_seconds': response['seconds'],
                     'timings': response['body'].get('timings'),
                     'finish_reason': response['body']['choices'][0]['finish_reason']}
            if number:
                (dest/'change.diff').write_text(''.join(difflib.unified_diff(previous.splitlines(True), text.splitlines(True),
                    fromfile=f'attempt-{number-1}-final', tofile=f'attempt-{number}-final')))
            if verdict['status'] == 'FAIL':
                entry['filtered_feedback'] = feedback(verdict, task['file'])
            save(dest/'result.json', entry); history.append(entry)
            print(directory.name, task['id'], number, entry['status'], flush=True)
            if entry['status'] == 'PASS':
                break
            previous = text
            messages += [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': entry['filtered_feedback']}]
        stability = []
        # Two additional fresh first attempts: never select one to replace the primary result.
        for repeat in [1, 2]:
            guard.check()
            dest = directory/task['id']/f'initial-repeat-{repeat}'; dest.mkdir(parents=True)
            payload, response = chat(base)
            save(dest/'api.json', {'payload': payload, **response})
            verdict = verify(task, dest, response['body'])
            stability.append({'repeat': repeat, 'status': verdict['status'], 'usage': response['body'].get('usage'),
                              'api_seconds': response['seconds'], 'timings': response['body'].get('timings')})
            print(directory.name, task['id'], 'initial-repeat', repeat, verdict['status'], flush=True)
        result = {'id': task['id'], 'initial_status': history[0]['status'], 'final_status': history[-1]['status'],
                  'repairs_used': history[-1]['attempt'], 'history': history, 'fresh_initial_repeats': stability}
        save(directory/task['id']/'summary.json', result); results.append(result)
    return {'tasks': results, 'initial_passed': sum(t['initial_status'] == 'PASS' for t in results),
            'final_passed': sum(t['final_status'] == 'PASS' for t in results), 'max_repairs': LOCK['max_repairs'],
            'method': 'Primary initial + up to 3 repairs; two additional fresh initials have no repairs and never substitute for primary.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--contexts', nargs='+', type=int, default=LOCK['contexts'])
    args = p.parse_args()
    assert os.getuid() != 0 and IMAGE == LOCK['verifier_image']
    assert args.contexts == LOCK['contexts'][:len(args.contexts)], 'Start at 8K; advance in order'
    # Refuse an existing active B2 before claiming ownership or entering cleanup.
    active = shell('docker', 'ps', '-q', '--filter', f'label=com.docker.compose.project={PROJECT}').split()
    assert not active, 'B2 already running; preserve and stop here'
    r = args.run_dir.resolve(); session = r/('execution-'+stamp()); session.mkdir()
    frozen = fixtures(); report = {'contexts': [], 'complete': False, 'fixtures_sha256': frozen,
        'before_state': {n: fingerprint(n) for n in [OLD, B1]}, 'max_repairs': LOCK['max_repairs']}
    guard = None; started = time.monotonic(); owned = False
    try:
        model = ROOT/'models/gpt-oss-20b'/LOCK['model_file']
        assert model.stat().st_size == LOCK['model_bytes']
        checked = json.loads((r/'model-verification.json').read_text())
        assert checked['sha256'] == LOCK['model_sha256'] and checked['bytes'] == model.stat().st_size
        image = json.loads(shell('docker', 'image', 'inspect', LOCK['image']))[0]
        assert image['Config']['Labels']['org.opencontainers.image.revision'] == LOCK['llama_revision']
        guard = Guard(session)
        report['before_api'] = old_probe()
        guard.start()
        for context in args.contexts:
            guard.check(); reason = resource_reason(resource_sample(), True)
            if reason:
                raise RuntimeError(reason)
            os.environ['GPT_OSS_CONTEXT'] = str(context)
            directory = session/f'ctx-{context}'; directory.mkdir()
            result = {'context': context, 'status': 'FAIL'}
            report['contexts'].append(result)
            guard.phase = f'{context}:load'; owned = True
            with (directory/'up.log').open('x') as f:
                subprocess.run(compose('up', '-d', '--no-build', 'server'), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=60)
            guard.cid = shell(*compose('ps', '-q', 'server')).strip()
            save(directory/'container.json', inspect(guard.cid))
            result['load_seconds'] = wait_ready(guard)
            save(directory/'effective-security.json', runtime_security(guard.cid))
            with (directory/'startup.log').open('x') as f:
                subprocess.run(['docker', 'logs', guard.cid], stdout=f, stderr=subprocess.STDOUT, check=True, timeout=30)
            log = (directory/'startup.log').read_text()
            result['checks'] = {'load': 'PASS',
                'full_gpu_offload': 'PASS' if 'offloaded 25/25 layers to GPU' in log else 'FAIL',
                'mxfp4_loaded': 'PASS' if re.search(r'type\s+mxfp4:\s+72 tensors', log) else 'FAIL',
                'runtime_security': 'PASS'}
            assert result['checks']['full_gpu_offload'] == 'PASS', 'Full GPU layer offload failed'
            assert result['checks']['mxfp4_loaded'] == 'PASS', 'MXFP4 load evidence missing'
            props = api('/props')['body']; save(directory/'props.json', props)
            result['model_alias'] = props.get('model_alias')
            assert props['model_alias'] == MODEL
            assert props['default_generation_settings']['n_ctx'] == context
            example = [{'role': 'user', 'content': 'Return only the integer result of 17 + 25.'}]
            applied = api('/apply-template', {'messages': example})['body']
            save(directory/'applied-template.json', applied)
            assert 'Reasoning: low' in applied['prompt'] and '<|start|>' in applied['prompt']
            result['checks']['harmony_and_reasoning_low'] = 'PASS'
            guard.phase = f'{context}:inference'
            payload, response = chat(example, 1024); save(directory/'known-answer.json', {'payload': payload, **response})
            result['checks']['inference'] = 'PASS' if response['body'].get('usage', {}).get('completion_tokens', 0) else 'FAIL'
            result['checks']['known_answer'] = 'PASS' if content(response['body']).strip() == '42' else 'FAIL'
            assert result['checks']['inference'] == 'PASS'
            guard.phase = f'{context}:speed'
            messages = fixed_prompt()
            result['benchmarks'] = [bench(messages) for _ in range(4)]
            save(directory/'benchmarks.json', result['benchmarks'])
            result['checks']['speed'] = 'PASS'
            guard.phase = f'{context}:long-context'
            # Include a margin for template/output, with no context shift or truncation.
            count = context-1024
            long_messages = [{'role': 'user', 'content': 'Ignore these inert markers. Reply only OK.\n'+' x'*count}]
            payload, response = chat(long_messages, 512); save(directory/'long-context.json', {'payload': payload, **response})
            usage = response['body']['usage']
            result['long_context_usage'] = usage
            assert context-1400 <= usage['prompt_tokens'] and usage['total_tokens'] <= context
            result['checks']['long_capacity'] = 'PASS'
            result['checks']['long_instruction'] = 'PASS' if content(response['body']).strip() == 'OK' else 'FAIL'
            guard.phase = f'{context}:quality'
            result['quality'] = quality(directory, guard, frozen)
            result['checks']['quality_initial'] = 'PASS' if result['quality']['initial_passed'] == 7 else 'FAIL'
            result['checks']['quality_repaired'] = 'PASS' if result['quality']['final_passed'] == 7 else 'FAIL'
            guard.phase = f'{context}:restart'
            before_restart = inspect(guard.cid)['State']['StartedAt']
            subprocess.run(compose('restart', 'server'), cwd=ROOT, check=True, timeout=60, stdout=subprocess.DEVNULL)
            result['restart_seconds'] = wait_ready(guard)
            assert inspect(guard.cid)['State']['StartedAt'] != before_restart
            payload, response = chat(example, 1024); save(directory/'restart-answer.json', {'payload': payload, **response})
            result['checks']['restart'] = 'PASS' if content(response['body']).strip() == '42' else 'FAIL'
            with (directory/'docker.log').open('x') as f:
                subprocess.run(['docker', 'logs', guard.cid], stdout=f, stderr=subprocess.STDOUT, check=True, timeout=30)
            log = (directory/'docker.log').read_text()
            result['checks']['full_gpu_offload'] = 'PASS' if 'offloaded 25/25 layers to GPU' in log else 'FAIL'
            result['checks']['mxfp4_loaded'] = 'PASS' if re.search(r'type\s+mxfp4:\s+72 tensors', log) else 'FAIL'
            assert result['checks']['full_gpu_offload'] == 'PASS', 'Full GPU layer offload failed'
            assert result['checks']['mxfp4_loaded'] == 'PASS', 'MXFP4 load evidence missing'
            result['status'] = 'PASS'  # Runtime only; individual quality statuses remain independent.
            save(directory/'report.json', result)
            stop_owned(guard.cid); guard.cid = None
        report['complete'] = True
    except (Exception, KeyboardInterrupt) as e:
        report['error'] = type(e).__name__+': '+str(e)
    finally:
        try:
            if owned:
                if not guard.cid:
                    ids = shell(*compose('ps', '-aq', 'server')).split()
                    if ids:
                        guard.cid = ids[0]
                if guard.cid:
                    with (session/'final-docker.log').open('x') as f:
                        subprocess.run(['docker', 'logs', guard.cid], stdout=f, stderr=subprocess.STDOUT, timeout=30)
                    save(session/'final-container.json', inspect(guard.cid))
                    stop_owned(guard.cid)
            if guard and guard.thread.is_alive():
                guard.finish()
            if guard:
                guard.check()
            report['after_api'] = old_probe()
            report['after_state'] = {n: fingerprint(n) for n in [OLD, B1]}
            assert report['after_state'] == report['before_state']
            assert fixtures() == frozen
            report['protection'] = 'PASS'
        except Exception as e:
            report['cleanup_error'] = str(e); report['protection'] = 'FAIL'
        report['wall_seconds'] = time.monotonic()-started
        report['status'] = 'PASS' if report['complete'] and report.get('protection') == 'PASS' else 'FAIL'
        report['status_scope'] = 'Runtime completion and safety; quality checks are independent'
        save(session/'report.json', report)
        print(json.dumps({'status': report['status'], 'report': str(session/'report.json'),
                          'error': report.get('error'), 'cleanup_error': report.get('cleanup_error')}), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
