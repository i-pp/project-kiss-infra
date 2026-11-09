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

"""Benign in-container checks performed before model code is accepted."""
import json
import os
from pathlib import Path
import resource
import socket
import subprocess

assert os.getuid() != 0
status = dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert int(status['CapEff'].strip(),16) == 0
assert status['NoNewPrivs'].strip() == '1'
assert status['Seccomp'].strip() == '2'
assert not Path('/dev/kfd').exists() and not Path('/dev/dri').exists()
assert not Path('/var/run/docker.sock').exists()
assert set(p.name for p in Path('/sys/class/net').iterdir()) == {'lo'}
sock = socket.socket();sock.settimeout(0.5)
try:
    sock.connect(('192.0.2.1',9))
except OSError:
    pass
else:
    raise AssertionError('Unexpected external connectivity')
finally:
    sock.close()
assert os.statvfs('/').f_flag & os.ST_RDONLY
assert os.statvfs('/suite').f_flag & os.ST_RDONLY
for mount in ['/work','/tmp']:
    line = next(s for s in Path('/proc/self/mountinfo').read_text().splitlines() if s.split()[4] == mount)
    assert ' - tmpfs ' in line, line
program = Path('/work/execution-probe')
program.write_text('#!/bin/sh\nexit 0\n')
program.chmod(0o700)
assert subprocess.run([str(program)],check=False).returncode == 0
cg = Path('/sys/fs/cgroup')
assert int((cg/'memory.max').read_text()) == 2*1024**3
assert int((cg/'memory.swap.max').read_text()) == 0
assert int((cg/'pids.max').read_text()) == 128
quota,period = map(int,(cg/'cpu.max').read_text().split())
assert quota/period == 4
assert resource.getrlimit(resource.RLIMIT_CORE) == (0,0)
assert resource.getrlimit(resource.RLIMIT_FSIZE) == (33554432,33554432)
print(json.dumps({'checks':'PASS','uid':os.getuid(),'seccomp':2,'cap_eff':0,'no_new_privs':1,
                  'network':'loopback only; external connect failed','memory_max':2*1024**3,
                  'swap_max':0,'pids_max':128,'cpu_limit':4,'writable_host_mounts':0}))
