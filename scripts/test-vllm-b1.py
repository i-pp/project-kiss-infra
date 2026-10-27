#!/usr/bin/env python3
"""Run only the B1 project, with host-side monitoring and append-only results.

Run under an existing Docker-authorized, non-root session. No installs, downloads,
changes to the existing server, or privilege workarounds are performed here.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OLD = 'project-kiss-phase2-llama-server-1'
PROJECT = 'project-kiss-vllm-b1'
GIB = 1024**3


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=20)


def compose(*args):
    return ['sh', str(ROOT/'scripts/vllm-compose.sh'), *args]


def api(port, path, body=None, timeout=10):
    start = time.monotonic()
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                                data=None if body is None else json.dumps(body).encode(),
                                headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read()
        return {'http_status': response.status, 'body': json.loads(payload) if payload else None,
                'seconds': time.monotonic()-start}


def old_state():
    c = json.loads(run('docker', 'inspect', OLD))[0]
    return {'id': c['Id'], 'image': c['Image'], 'started_at': c['State']['StartedAt'],
            'restart_count': c['RestartCount'], 'running': c['State']['Running'],
            'health': c['State'].get('Health', {}).get('Status')}


def sample():
    result = {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    result['linux'] = {line.split(':')[0]: int(line.split()[1])*1024
                       for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.split(':')[0] in ['MemTotal', 'MemAvailable', 'SwapFree']}
    result['gpu'] = {str(p): int(p.read_text())
                     for p in Path('/sys/class/drm').glob('card*/device/mem_info_*')
                     if p.name in ['mem_info_vram_used', 'mem_info_vram_total',
                                   'mem_info_gtt_used', 'mem_info_gtt_total']}
    for suffix in ['gpu_busy_percent', 'mem_busy_percent']:
        result[suffix] = {str(p): p.read_text().strip()
                          for p in Path('/sys/class/drm').glob(f'card*/device/{suffix}')}
    return result


def new_ids():
    return run('docker', 'ps', '-aq', '--filter',
               f'label=com.docker.compose.project={PROJECT}').split()


def stop_new():
    ids = new_ids()
    if ids:
        subprocess.run(['docker', 'stop', '-t', '10', *ids], timeout=50, check=True)


class Guard:
    def __init__(self, directory):
        self.directory = directory
        self.initial = old_state()
        assert self.initial['running'] and self.initial['health'] == 'healthy'
        api(8080, '/health')
        self.done = threading.Event()
        self.failed = None
        self.phase = 'preflight'
        self.thread = threading.Thread(target=self.watch, daemon=True)
        cursor = run('journalctl', '-k', '-n', '0', '--show-cursor', '--no-pager')
        self.journal_cursor = cursor.split('-- cursor: ', 1)[1].strip()

    def check_resources(self, record):
        if record['linux']['MemAvailable'] < 16*GIB:
            return 'Linux MemAvailable below 16 GiB'
        used = sum(v for k, v in record['gpu'].items() if k.endswith('/mem_info_vram_used'))
        if used > 58*GIB:
            return 'Total GPU VRAM use above 58 GiB'
        return None

    def start(self):
        reason = self.check_resources(sample())
        if reason:
            raise RuntimeError('Preflight refused: '+reason)
        self.thread.start()

    def watch(self):
        low = 0
        try:
            with (self.directory/'memory.jsonl').open('x') as f:
                while not self.done.is_set():
                    s = sample()
                    s['phase'] = self.phase
                    current = old_state()
                    if current != self.initial:
                        raise RuntimeError('Existing 30B state changed: '+json.dumps(current))
                    api(8080, '/health', timeout=5)
                    messages = run('journalctl', '-k', '--after-cursor', self.journal_cursor,
                                   '--show-cursor', '--no-pager', '-o', 'json')
                    for line in messages.splitlines():
                        if line.startswith('-- cursor: '):
                            self.journal_cursor = line.split('-- cursor: ', 1)[1]
                        elif line.startswith('{'):
                            message = json.loads(line).get('MESSAGE', '')
                            if re.search(r'amdgpu.*(GPU reset|GPU fault|ring .*timeout|VM_L2_PROTECTION)|Out of memory: Killed process', message, re.I):
                                raise RuntimeError('Kernel safety event: '+message)
                    reason = self.check_resources(s)
                    low = low+1 if reason else 0
                    ids = new_ids()
                    s['containers'] = {}
                    if ids:
                        for c in json.loads(run('docker', 'inspect', *ids)):
                            s['containers'][c['Name']] = c['State']
                            if c['State'].get('OOMKilled'):
                                raise RuntimeError('New container OOMKilled')
                        # Raw cgroup memory includes page cache, unlike docker stats.
                        for name, state in s['containers'].items():
                            pid = state.get('Pid', 0)
                            if pid:
                                cg = Path(f'/proc/{pid}/cgroup').read_text().split('0::')[-1].strip()
                                base = Path('/sys/fs/cgroup')/cg.lstrip('/')
                                state['cgroup_memory'] = {key: (base/key).read_text().strip()
                                    for key in ['memory.current', 'memory.peak', 'memory.events']
                                    if (base/key).is_file()}
                                events = state['cgroup_memory'].get('memory.events', '')
                                if any(int(line.split()[1]) for line in events.splitlines()
                                       if line.split()[0] in ['oom', 'oom_kill']):
                                    raise RuntimeError('New cgroup OOM event')
                    f.write(json.dumps(s)+'\n'); f.flush()
                    if low >= 3:
                        raise RuntimeError('Sustained pressure: '+reason)
                    self.done.wait(2)
        except Exception as e:
            self.failed = str(e)
            (self.directory/'safety-stop.json').write_text(json.dumps({'reason': self.failed}))
            stop_new()

    def finish(self):
        self.done.set()
        self.thread.join(timeout=30)
        assert not self.thread.is_alive(), 'Monitor did not terminate'
        if self.failed:
            raise RuntimeError(self.failed)


def existing_api():
    return api(8080, '/v1/chat/completions', {
        'model': 'kiss-qwen3-coder-30b',
        'messages': [{'role': 'user', 'content': 'Return only the integer result of 17 + 25.'}],
        'temperature': 0, 'max_tokens': 16}, timeout=60)


def bounded(command, path, seconds):
    start = time.monotonic()
    with path.open('x') as f:
        p = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=seconds)
    if p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}); see {path}')
    return time.monotonic()-start


def wait_server(guard, seconds=360):
    start = time.monotonic()
    while time.monotonic()-start < seconds:
        if guard.failed:
            raise RuntimeError(guard.failed)
        ids = new_ids()
        servers = [c for c in json.loads(run('docker', 'inspect', *ids))
                   if c['Config']['Labels'].get('com.docker.compose.service') == 'server'] if ids else []
        if servers and not servers[0]['State']['Running']:
            raise RuntimeError('vLLM server exited before readiness')
        try:
            api(8081, '/health', timeout=2)
            return time.monotonic()-start
        except Exception:
            guard.done.wait(2)
    raise TimeoutError('vLLM readiness timeout')


def benchmark():
    # Read-only code output; it is never executed on the host.
    prompt = 'Write a short C function unsigned sum_u32(const unsigned *a, unsigned n) that returns the unsigned sum. Output code only.'
    body = {'model': 'kiss-vllm-qwen25-coder-1p5b',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0, 'max_tokens': 128, 'stream': True,
            'stream_options': {'include_usage': True}}
    start = time.monotonic()
    first = None
    last_content = None
    chunks = []
    req = urllib.request.Request('http://127.0.0.1:8081/v1/chat/completions',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        for line in response:
            if not line.startswith(b'data: ') or line.strip() == b'data: [DONE]':
                continue
            chunk = json.loads(line[6:])
            now = time.monotonic()
            chunks.append(chunk)
            if any(c.get('delta', {}).get('content') for c in chunk.get('choices', [])):
                first = first or now
                last_content = now
    end = time.monotonic()
    usage = next(c['usage'] for c in reversed(chunks) if c.get('usage'))
    assert first is not None and usage['completion_tokens'] > 1
    return {'request': body, 'chunks': chunks, 'usage': usage,
            'wall_seconds': end-start, 'ttft_seconds': first-start,
            'decode_tokens_per_second': (usage['completion_tokens']-1)/(last_content-first),
            'decode_metric': '(completion_tokens - 1) / (last_content_time - first_content_time)',
            'end_to_end_tokens_per_second': usage['completion_tokens']/(end-start)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['probe', 'serve'])
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    assert os.getuid() != 0
    directory = args.run_dir.resolve()/(args.mode+'-'+stamp())
    directory.mkdir(parents=True, exist_ok=False)
    report = {'mode': args.mode, 'status': 'FAIL', 'start_utc': stamp()}
    guard = None
    owned = False
    start = time.monotonic()
    try:
        # Read-only inspection establishes that this is a new, separate project.
        assert not any(json.loads(run('docker', 'inspect', cid))[0]['State']['Running'] for cid in new_ids()), 'B1 project already running'
        report['before_state'] = old_state()
        report['before_api'] = existing_api()
        guard = Guard(directory)
        guard.start()
        owned = True
        if args.mode == 'probe':
            name = 'project-kiss-vllm-b1-probe-'+stamp().lower()
            report['seconds'] = bounded(compose('--profile', 'check', 'run', '--no-deps',
                 '--name', name, 'gpu-check'), directory/'gpu-check.log', 180)
            report['container'] = json.loads(run('docker', 'inspect', name))[0]
        else:
            guard.phase = 'initial_load'
            report['up_seconds'] = bounded(compose('up', '-d', '--no-build', 'server'), directory/'up.log', 60)
            server_id = run(*compose('ps', '-q', 'server')).strip()
            server = json.loads(run('docker', 'inspect', server_id))[0]
            assert server['NetworkSettings']['Ports'].get('8000/tcp') == [{'HostIp': '127.0.0.1', 'HostPort': '8081'}], 'Localhost port mapping was not created'
            assert server['Config']['User'].split(':')[0] != '0'
            assert server['HostConfig']['ReadonlyRootfs']
            assert server['HostConfig']['CapDrop'] == ['ALL']
            assert 'no-new-privileges:true' in server['HostConfig']['SecurityOpt']
            assert not server['HostConfig']['Privileged']
            assert server['HostConfig']['NetworkMode'] != 'host'
            report['security_inspect'] = server
            report['load_seconds'] = wait_server(guard)
            guard.phase = 'short_generation'
            report['models'] = api(8081, '/v1/models')
            report['runs'] = [benchmark() for _ in range(3)]
            guard.phase = 'long_prompt'
            context_body = {'model': 'kiss-vllm-qwen25-coder-1p5b',
                'messages': [{'role': 'user', 'content': 'Ignore the following repeated marker and reply OK.\n'+' x'*min(7000, max(1, int(os.environ.get('VLLM_CONTEXT', '8192'))-1000))}],
                'temperature': 0, 'max_tokens': 16}
            report['long_prompt'] = api(8081, '/v1/chat/completions', context_body, timeout=120)
            expected_min = min(6500, max(1, int(os.environ.get('VLLM_CONTEXT', '8192'))-1100))
            assert report['long_prompt']['body']['usage']['prompt_tokens'] >= expected_min
            assert report['long_prompt']['body']['usage']['total_tokens'] <= int(os.environ.get('VLLM_CONTEXT', '8192'))
            # Preserve metrics with TTFT/prefill/decode histograms where available.
            with urllib.request.urlopen('http://127.0.0.1:8081/metrics', timeout=5) as response:
                (directory/'metrics.txt').write_bytes(response.read())
            report['container_before_restart'] = json.loads(run('docker', 'inspect', *new_ids()))
            guard.phase = 'restart_load'
            bounded(compose('restart', 'server'), directory/'restart.log', 60)
            report['restart_load_seconds'] = wait_server(guard)
            guard.phase = 'after_restart_generation'
            report['after_restart_run'] = benchmark()
            report['container_after_restart'] = json.loads(run('docker', 'inspect', *new_ids()))
        report['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as e:
        report['error'] = type(e).__name__+': '+str(e)
    finally:
        # B1 is a smoke test; stop only its own containers on both success and failure.
        try:
            ids = new_ids() if owned else []
            if ids:
                with (directory/'docker.log').open('x') as f:
                    subprocess.run(compose('logs', '--no-color'), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=20)
                report['containers_final'] = json.loads(run('docker', 'inspect', *ids))
            if owned:
                stop_new()
            if guard:
                guard.finish()
            report['after_api'] = existing_api()
            report['after_state'] = old_state()
            if 'before_state' in report:
                assert report['after_state'] == report['before_state'], 'Existing 30B state changed'
        except Exception as e:
            report['status'] = 'FAIL'
            report['cleanup_or_protection_error'] = str(e)
        report['wall_seconds'] = time.monotonic()-start
        (directory/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
        print(json.dumps({'status': report['status'], 'report': str(directory/'report.json'),
                          'error': report.get('error'), 'cleanup_error': report.get('cleanup_or_protection_error')}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
