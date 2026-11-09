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

"""Phase 2C driver: adds objects only, never operates the inference project."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT/'dev/x86_64'
LOCK = json.loads((DEV/'versions.lock.json').read_text())
IMAGE = os.environ.get('DEV_IMAGE', 'project-kiss-x86-dev:phase2c-20261027')
if not re.fullmatch(r'project-kiss-x86-dev:[A-Za-z0-9_.-]+', IMAGE):
    raise SystemExit('Use an explicit project-kiss-x86-dev:<tag>')


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write('\n')


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def inspect_image(name):
    return json.loads(run('docker', 'image', 'inspect', name))[0]


def parent_check():
    parent = inspect_image(LOCK['parent'])
    if parent['Id'] != LOCK['parent_id']:
        raise SystemExit('Parent ID mismatch: stop')
    return parent


def assets():
    ids = run('docker', 'ps', '-aq', '--no-trunc').split()
    records = json.loads(run('docker', 'inspect', *ids)) if ids else []
    containers = {r['Id']: {k: r[k] for k in ['Name', 'Image', 'Config', 'HostConfig', 'NetworkSettings']}
                  | {'StartedAt': r['State']['StartedAt'], 'Running': r['State']['Running'],
                     'RestartCount': r['RestartCount'], 'Health': r['State'].get('Health', {}).get('Status')}
                  for r in records}
    return {'containers': containers,
            'images': sorted(set(run('docker', 'image', 'ls', '-q', '--no-trunc').split())),
            'cache_ids': sorted(re.findall(r'^ID:\s+(\S+)', run('docker', 'builder', 'du', '--verbose'), re.M)),
            'networks': run('docker', 'network', 'ls', '--no-trunc'),
            'host': {p: sha(Path(p)) for p in ['/var/lib/dpkg/status', '/etc/os-release',
                     '/etc/apt/sources.list.d/ubuntu.sources', '/etc/docker/daemon.json'] if Path(p).is_file()},
            'disk': run('df', '-B1', str(ROOT)), 'docker_disk': run('docker', 'system', 'df')}


def snapshot(dest):
    dest.mkdir(parents=True, exist_ok=False)
    tracked = [p for p in run('git', 'ls-files', '-z').split('\0') if p]
    assert tracked and not any(p.startswith(('website/', 'i-pp-website/')) for p in tracked)
    logs = [p for p in (ROOT/'logs').rglob('*')
            if p.is_file() and not p.is_symlink() and not p.is_relative_to(ROOT/'logs/dev-targets')]
    models = {str(p.relative_to(ROOT)): [p.stat().st_size, p.stat().st_mtime_ns]
              for p in (ROOT/'models').rglob('*') if p.is_file()}
    before = assets() | {'timestamp': stamp(), 'files': {p: sha(ROOT/p) for p in tracked},
             'logs': {str(p.relative_to(ROOT)): sha(p) for p in logs}, 'models': models,
             'parent': parent_check(), 'commit': run('git', 'rev-parse', 'HEAD').strip()}
    (dest/'README.before').write_bytes((ROOT/'README.md').read_bytes())
    save(dest/'before.json', before)
    print(f'Protected {len(tracked)} source files and {len(logs)} existing logs: {dest}')


def verify(dest):
    before = json.loads((dest/'before.json').read_text())
    after = assets()
    failures = []
    for name, expected in (before['files'] | before['logs']).items():
        path = ROOT/name
        if name == 'README.md':
            good = path.read_bytes().startswith((dest/'README.before').read_bytes())
        else:
            good = path.is_file() and sha(path) == expected
        if not good:
            failures.append(name)
    for name, expected in before['models'].items():
        p = ROOT/name
        if not p.is_file() or [p.stat().st_size, p.stat().st_mtime_ns] != expected:
            failures.append(name)
    for key in ['host', 'networks']:
        if after[key] != before[key]: failures.append(key)
    for key in ['images', 'cache_ids']:
        if not set(before[key]) <= set(after[key]): failures.append(key)
    for cid, value in before['containers'].items():
        if after['containers'].get(cid) != value: failures.append('container '+cid)
    report = {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
              'source_count': len(before['files']), 'log_count': len(before['logs']),
              'after': after, 'parent': parent_check()}
    save(dest/('protection-'+stamp()+'.json'), report)
    print(json.dumps({k:report[k] for k in ['status','failures','source_count','log_count']}, indent=2))
    if failures: raise SystemExit(1)


def compose(*args):
    if os.getuid() == 0: raise SystemExit('Run as the normal Docker user')
    env = os.environ | {'LOCAL_UID': str(os.getuid()), 'LOCAL_GID': str(os.getgid()),
                        'DEV_ROOT': str(ROOT), 'DEV_IMAGE': IMAGE}
    return ['docker', 'compose', '-f', str(DEV/'compose.yaml'), *args], env


def test(dest):
    parent = parent_check()
    image = inspect_image(IMAGE)
    assert image['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] == parent['RootFS']['Layers']
    session = dest/('test-'+stamp())
    session.mkdir()
    (ROOT/'.cache/dev-x86_64').mkdir(parents=True, exist_ok=True)
    save(session/'image.json', image)
    cfg, env = compose('config', '--format', 'json')
    save(session/'compose-effective.json', json.loads(subprocess.check_output(cfg, env=env)))
    files = [p for base in [ROOT/'dev/common', DEV, ROOT/'dev/aarch64'] for p in base.rglob('*')
             if p.is_file() and '.cache' not in p.parts and '__pycache__' not in p.parts]
    files += [ROOT/'scripts'/x for x in ['test-dev-targets.py','test-dev-aarch64.py','dev-x86_64.py','dev-x86_64.sh']]
    save(session/'source-sha256.json', {str(p.relative_to(ROOT)):sha(p) for p in files})
    exits = {}
    for service, script, label in [('dev', 'test-dev-targets.py', 'targets'),
                                  ('aarch64-regression', 'test-dev-aarch64.py', 'aarch64-regression')]:
        output = session/label
        output.mkdir()
        name = 'project-kiss-target-smoke-'+stamp().lower()
        cmd, env = compose('run', '--rm', '--no-deps', '-T', '--name', name, service,
            'python3', '/src/scripts/'+script, '/logs/'+str(output.relative_to(ROOT/'logs/dev-targets')))
        try:
            with (output/'console.txt').open('x') as console:
                result = subprocess.run(cmd, env=env, cwd=ROOT, stdout=console, stderr=subprocess.STDOUT, timeout=600)
            exits[label] = result.returncode
        finally:
            found = run('docker','ps','-aq','--filter','name=^/'+name+'$').split()
            if found: subprocess.run(['docker','rm','-f',*found], check=True, stdout=subprocess.DEVNULL)
        print(f'{label}: rc={result.returncode}; {output}', flush=True)
    save(session/'runner-result.json', exits)
    if any(exits.values()): raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['snapshot','build','test','verify','config'])
    parser.add_argument('run_dir', nargs='?')
    args = parser.parse_args()
    parent_check()
    dest = Path(args.run_dir).resolve() if args.run_dir else None
    if args.action != 'config' and (dest is None or not dest.is_relative_to(ROOT/'logs/dev-targets')):
        raise SystemExit('Specify a new/protected run directory under logs/dev-targets/')
    if args.action == 'snapshot': snapshot(dest)
    elif args.action == 'verify': verify(dest)
    elif args.action == 'test':
        assert (dest/'before.json').exists()
        test(dest)
    elif args.action == 'build':
        assert (dest/'before.json').exists()
        tags = run('docker','image','ls','--format','{{.Repository}}:{{.Tag}}').split()
        if IMAGE in tags: raise SystemExit('Preserve existing image tag; choose a new DEV_IMAGE')
        log = dest/('build-'+stamp()+'.txt')
        with log.open('x') as output:
            result = subprocess.run(['docker','build','--no-cache','--pull=false','--progress=plain',
                '--tag',IMAGE,str(DEV)], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        print(f'Build rc={result.returncode}; {log}')
        if result.returncode == 0: save(dest/'built-image.json', inspect_image(IMAGE))
        raise SystemExit(result.returncode)
    else:
        cmd, env = compose('config')
        subprocess.run(cmd, env=env, check=True)


if __name__ == '__main__': main()
