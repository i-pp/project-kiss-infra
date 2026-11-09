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

"""Trusted host-side Docker control. Candidate code never executes on the host."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import uuid

IMAGE = 'sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c'
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_LIMIT = 1024 * 1024


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=30)


def stop_container(cid):
    if not json.loads(docker('inspect', cid))[0]['State']['Running']:
        return
    result = subprocess.run(['docker', 'kill', cid], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=30)
    if result.returncode and json.loads(docker('inspect', cid))[0]['State']['Running']:
        raise RuntimeError(result.stderr)


def execute(command, candidate=None, seconds=120, memory=2*1024**3, output_limit=OUTPUT_LIMIT):
    """Fresh container, no writable host mount; always remove only its exact ID."""
    if os.getuid() == 0:
        raise RuntimeError('Run the PoC as a non-root host user')
    name = 'kiss-repair-' + uuid.uuid4().hex
    args = ['create', '--name', name, '--network', 'none', '--read-only',
            '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--pids-limit', '128',
            '--memory', str(memory), '--memory-swap', str(memory), '--cpus', '4',
            '--ulimit', 'core=0', '--ulimit', 'fsize=33554432', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
            '--tmpfs', '/work:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--mount', f'type=bind,src={ROOT / "evaluation/coder"},dst=/suite,readonly',
            '--workdir', '/work']
    if candidate is not None:
        candidate = Path(candidate).resolve(strict=True)
        if not candidate.is_dir() or not candidate.is_relative_to(ROOT / 'logs'):
            raise RuntimeError('Candidate directory must be under project logs/')
        args += ['--mount', f'type=bind,src={candidate},dst=/candidate,readonly']
    cid = docker(*args, IMAGE, *command).strip()
    process = None
    started = time.monotonic()
    reason = None
    data = bytearray()
    try:
        configuration = json.loads(docker('inspect', cid))[0]
        h = configuration['HostConfig']
        assert not h['Privileged'] and h['ReadonlyRootfs'] and h['NetworkMode'] == 'none'
        assert h['Memory'] == memory and h['MemorySwap'] == memory
        assert h['PidsLimit'] == 128 and h['NanoCpus'] == 4_000_000_000
        assert not h['Devices'] and not h['DeviceRequests'] and not h['PortBindings']
        assert h['CapDrop'] == ['ALL'] and not h['CapAdd']
        assert 'no-new-privileges' in h['SecurityOpt']
        assert configuration['Config']['User'].split(':')[0] != '0'
        assert all(not mount['RW'] for mount in configuration['Mounts'] if mount['Type'] == 'bind')
        process = subprocess.Popen(['docker', 'start', '-a', cid], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            if time.monotonic() - started > seconds:
                reason = 'wall_timeout'
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                available = output_limit - len(data)
                data.extend(chunk[:available])
                if len(chunk) > available:
                    reason = 'output_limit'
                    break
            if reason:
                break
        selector.close()
        if reason:
            # Do not keep an attached Docker client blocked on unread output.
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stdout.close()
            stop_container(cid)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            stop_container(cid)
            process.kill()
            process.wait(timeout=10)
            reason = reason or 'wall_timeout'
        state = json.loads(docker('inspect', cid))[0]['State']
        return {'container_id': cid, 'host_config': h, 'state': state,
                'wall_seconds': time.monotonic()-started, 'limit_reason': reason,
                'output': data.decode('utf-8', errors='replace')}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        # Exact newly-created ID, never a pre-existing server or volume.
        docker('rm', '-f', cid)
