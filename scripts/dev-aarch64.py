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

"""Small host-side driver. Never operates on the inference Compose project."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / 'dev/aarch64'
PARENT = 'project-kiss-code-eval:20261027'
PARENT_ID = 'sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c'
IMAGE = os.environ.get('DEV_IMAGE', 'project-kiss-aarch64-dev:phase1-20261027')
if not re.fullmatch(r'project-kiss-aarch64-dev:[a-zA-Z0-9_.-]+', IMAGE):
    raise SystemExit('Use an explicit project-kiss-aarch64-dev:<tag>')


def run(*args):
    return subprocess.check_output(args, text=True, cwd=ROOT)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def write_new(path, obj):
    with path.open('x') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write('\n')


def parent_check():
    actual = run('docker', 'image', 'inspect', PARENT, '--format', '{{.Id}}').strip()
    if actual != PARENT_ID:
        raise SystemExit(f'Parent identity mismatch: {actual}')


def containers():
    ids = run('docker', 'ps', '-aq', '--no-trunc').split()
    records = json.loads(run('docker', 'inspect', *ids)) if ids else []
    return {r['Id']: {k: r[k] for k in ('Name', 'Image', 'Config', 'HostConfig', 'NetworkSettings')}
            | {'StartedAt': r['State']['StartedAt'], 'Running': r['State']['Running'],
               'RestartCount': r['RestartCount'], 'Health': r['State'].get('Health', {}).get('Status')}
            for r in records}


def cache_ids():
    raw = run('docker', 'builder', 'du', '--verbose')
    return sorted(re.findall(r'^ID:\s+(\S+)', raw, re.MULTILINE))


def host_files():
    paths = ['/var/lib/dpkg/status', '/etc/os-release', '/etc/default/grub',
             '/etc/docker/daemon.json', '/etc/apt/sources.list.d/ubuntu.sources']
    return {p: digest(Path(p)) for p in paths if Path(p).is_file()}


def snapshot(dest):
    parent_check()
    files = {}
    for base in ['AGENTS.md', '.gitignore', 'README.md', 'compose.yaml', 'scripts',
                 'evaluation', 'docs', 'logs']:
        p = ROOT / base
        for f in ([p] if p.is_file() else sorted(p.rglob('*'))):
            rel = f.relative_to(ROOT).as_posix()
            if (not f.is_file() or f.is_symlink() or '__pycache__' in f.parts
                    or rel.startswith('logs/dev-aarch64/')
                    or rel in ['scripts/dev-aarch64.py', 'scripts/dev-aarch64.sh',
                               'scripts/test-dev-aarch64.py', 'docs/dev-aarch64.md']):
                continue
            files[rel] = digest(f)
    # Models are never mounted or read by this toolchain; record metadata without hashing 18 GB.
    models = {str(p.relative_to(ROOT)): [p.stat().st_size, p.stat().st_mtime_ns]
              for p in (ROOT / 'models').rglob('*') if p.is_file()}
    images = run('docker', 'image', 'ls', '-q', '--no-trunc').split()
    write_new(dest / 'before.json', {'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
              'parent': PARENT_ID, 'files': files, 'models': models, 'host': host_files(),
              'containers': containers(), 'images': sorted(set(images)), 'cache_ids': cache_ids(),
              'networks': run('docker', 'network', 'ls', '--no-trunc'),
              'disk': run('df', '-B1', str(ROOT)), 'docker_disk': run('docker', 'system', 'df')})
    print(f'Protected snapshot: {dest / "before.json"}')


def verify(dest):
    before = json.loads((dest / 'before.json').read_text())
    parent_check()
    failures = []
    for rel, expected in before['files'].items():
        p = ROOT / rel
        if rel == 'README.md':
            # README additions are approved; original content must remain a byte-for-byte prefix.
            old = dest / 'README.before'
            if not old.exists() or not p.read_bytes().startswith(old.read_bytes()):
                failures.append(rel)
        elif not p.is_file() or digest(p) != expected:
            failures.append(rel)
    for rel, expected in before['models'].items():
        p = ROOT / rel
        if not p.is_file() or [p.stat().st_size, p.stat().st_mtime_ns] != expected:
            failures.append(rel)
    if host_files() != before['host']:
        failures.append('host package/config fingerprint')
    current = containers()
    for cid, expected in before['containers'].items():
        if current.get(cid) != expected:
            failures.append(f'container {cid}')
    images = set(run('docker', 'image', 'ls', '-q', '--no-trunc').split())
    if not set(before['images']) <= images:
        failures.append('existing image missing')
    if not set(before['cache_ids']) <= set(cache_ids()):
        failures.append('existing build cache ID missing')
    if run('docker', 'network', 'ls', '--no-trunc') != before['networks']:
        failures.append('Docker network list changed')
    report = {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
              'protected_file_count': len(before['files']), 'containers': current,
              'disk': run('df', '-B1', str(ROOT)), 'docker_disk': run('docker', 'system', 'df'),
              'image': json.loads(run('docker', 'image', 'inspect', IMAGE)) if IMAGE in
                       run('docker', 'image', 'ls', '--format', '{{.Repository}}:{{.Tag}}').split() else None}
    write_new(dest / ('protection-' + dt.datetime.now(dt.timezone.utc).strftime('%H%M%S%f') + '.json'), report)
    print(json.dumps({k: report[k] for k in ('status', 'failures', 'protected_file_count')}, indent=2))
    if failures:
        raise SystemExit(1)


def compose(*args):
    env = os.environ.copy()
    if os.getuid() == 0:
        raise SystemExit('Run as the normal Docker user, not root')
    env.update(LOCAL_UID=str(os.getuid()), LOCAL_GID=str(os.getgid()),
               DEV_ROOT=str(ROOT), DEV_IMAGE=IMAGE)
    return ['docker', 'compose', '-f', str(DEV / 'compose.yaml'), *args], env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['snapshot', 'build', 'test', 'shell', 'verify', 'config'])
    ap.add_argument('run_dir', nargs='?')
    ns = ap.parse_args()
    parent_check()
    dest = Path(ns.run_dir).resolve() if ns.run_dir else None
    if dest and not dest.is_relative_to(ROOT / 'logs/dev-aarch64'):
        raise SystemExit('Run directory must be under logs/dev-aarch64/')
    if ns.action in ['snapshot', 'verify', 'build', 'test'] and dest is None:
        raise SystemExit('Specify the protected run directory under logs/dev-aarch64/')
    if ns.action == 'snapshot':
        if not dest:
            raise SystemExit('Specify a new run directory')
        dest.mkdir(parents=True, exist_ok=False)
        (dest / 'README.before').write_bytes((ROOT / 'README.md').read_bytes())
        snapshot(dest)
    elif ns.action == 'verify':
        verify(dest)
    elif ns.action == 'build':
        if run('docker', 'image', 'ls', '--format', '{{.Repository}}:{{.Tag}}').split().count(IMAGE):
            raise SystemExit('Development tag already exists: preserve it; use a new explicit tag after review')
        config = json.loads((DEV / 'versions.lock.json').read_text())
        ca = DEV / '.cache/ca-certificates.deb'
        ca.parent.mkdir(exist_ok=True)
        if not ca.exists():
            url = f"https://snapshot.ubuntu.com/ubuntu/{config['ubuntu_snapshot']}/{config['ca_bootstrap_file']}"
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read(1024*1024 + 1)
            if len(data) > 1024*1024 or hashlib.sha256(data).hexdigest() != config['ca_bootstrap_sha256']:
                raise SystemExit('CA bootstrap SHA256/size mismatch')
            with ca.open('xb') as f:
                f.write(data)
        if digest(ca) != config['ca_bootstrap_sha256']:
            raise SystemExit('Cached CA bootstrap SHA256 mismatch')
        command = ['docker', 'build', '--no-cache', '--pull=false', '--progress=plain',
                   '--tag', IMAGE, str(DEV)]
        log = dest / ('build-' + dt.datetime.now(dt.timezone.utc).strftime('%H%M%S%f') + '.log')
        with log.open('x') as out:
            result = subprocess.run(command, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        print(f'Build rc={result.returncode}; log: {log}')
        if result.returncode == 0:
            write_new(dest / 'built-image.json', json.loads(run('docker', 'image', 'inspect', IMAGE)))
        raise SystemExit(result.returncode)
    elif ns.action == 'config':
        command, env = compose('config')
        subprocess.run(command, env=env, check=True)
    else:
        out = ROOT / '.cache/dev-aarch64'
        out.mkdir(parents=True, exist_ok=True)
        if ns.action == 'test':
            if not dest or not (dest / 'before.json').exists():
                raise SystemExit('Specify the protected run directory')
            result_dir = dest / ('test-' + dt.datetime.now(dt.timezone.utc).strftime('%H%M%S%f'))
            result_dir.mkdir()
            parent = json.loads(run('docker', 'image', 'inspect', PARENT))[0]
            image = json.loads(run('docker', 'image', 'inspect', IMAGE))[0]
            assert image['RootFS']['Layers'][:len(parent['RootFS']['Layers'])] == parent['RootFS']['Layers']
            write_new(result_dir / 'image.json', image)
            # Record exactly which source version was used by this run.
            write_new(result_dir / 'source-sha256.json', {
                str(p.relative_to(ROOT)): digest(p)
                for p in [*(DEV.rglob('*')), ROOT/'scripts/test-dev-aarch64.py',
                          ROOT/'scripts/dev-aarch64.py', ROOT/'scripts/dev-aarch64.sh']
                if p.is_file() and '.cache' not in p.parts and '__pycache__' not in p.parts})
            command, env = compose('run', '--rm', '--no-deps', '-T', 'dev',
                'python3', '/src/scripts/test-dev-aarch64.py', '/logs/' + str(result_dir.relative_to(ROOT / 'logs/dev-aarch64')))
            # Bound the complete run as well as each compiler/emulator command.
            name = 'project-kiss-dev-smoke-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S%f')
            pos = command.index('run') + 1
            command[pos:pos] = ['--name', name]
            with (result_dir/'compose-effective.json').open('x') as f:
                cfg, _ = compose('config', '--format', 'json')
                subprocess.run(cfg, env=env, stdout=f, check=True)
            try:
                result = subprocess.run(command, env=env, cwd=ROOT, timeout=600)
            finally:
                # Only remove this invocation's NEW one-shot container, if a failed
                # daemon start/timeout prevented --rm. Never touch pre-existing IDs.
                found = run('docker', 'ps', '-aq', '--filter', 'name=^/'+name+'$').split()
                if found:
                    subprocess.run(['docker', 'rm', '-f', *found], check=True, stdout=subprocess.DEVNULL)
            if result.returncode:
                raise SystemExit(result.returncode)
        else:
            command, env = compose('run', '--rm', '--no-deps', 'dev', 'bash')
            subprocess.run(command, env=env, check=True, cwd=ROOT)


if __name__ == '__main__':
    main()
