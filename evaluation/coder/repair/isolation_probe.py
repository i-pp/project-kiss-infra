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
