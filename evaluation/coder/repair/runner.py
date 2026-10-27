"""Trusted container runner. Reuses the unchanged independent coder fixtures."""
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time

os.chdir('/work')
os.environ['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
TASKS = {'c_parse':'c_parse.c', 'cpp_alias':'cpp_alias.cpp', 'posix_write':'posix_write.c',
         'rust_prefix':'rust_prefix.rs', 'aarch64_sum':'aarch64_sum.S',
         'neon_sad':'neon_sad.c', 'neon_dot':'neon_dot.c'}
task = sys.argv[1]
if task not in TASKS: raise SystemExit('Unknown task')
source = '/candidate/' + TASKS[task]
steps = []


class Failure(Exception):
    pass


def step(phase, argv):
    started = time.monotonic()
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    data = bytearray(); reason = None
    while selector.get_map():
        if time.monotonic()-started > 30:
            reason = 'step_timeout'; break
        for key, _ in selector.select(timeout=0.1):
            chunk = os.read(key.fileobj.fileno(),65536)
            if not chunk:
                selector.unregister(key.fileobj); continue
            available = 65536-len(data)
            data.extend(chunk[:available])
            if len(chunk)>available:
                reason = 'step_output_limit'; break
        if reason: break
    selector.close()
    if reason:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=2)
        reason = reason or 'step_timeout'
    record = {'phase':phase, 'argv':argv, 'returncode':process.returncode,
              'limit_reason':reason,'wall_seconds':time.monotonic()-started,
              'output':data.decode('utf-8',errors='replace')}
    steps.append(record)
    if process.returncode or reason: raise Failure(phase)
    return record['output']


c = ['-std=c11','-O2','-Wall','-Wextra','-Werror','-D_POSIX_C_SOURCE=200809L']
san = ['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
marker = None
try:
    if task == 'c_parse':
        step('compile_candidate',['gcc',*c,*san,'-c',source,'-o','candidate.o'])
        step('link_tests',['g++','-std=c++20','-O2',*san,'/suite/c_parse_test.cpp','candidate.o','-o','test'])
        marker = 'C parser: boundary cases + 60000 independent from_chars comparisons PASS'
    elif task == 'cpp_alias':
        cpp = ['-std=c++20','-O2','-Wall','-Wextra','-Werror','-D_GLIBCXX_DEBUG',*san]
        step('compile_candidate',['g++',*cpp,'-c',source,'-o','candidate.o'])
        step('link_tests',['g++',*cpp,'/suite/cpp_alias_test.cpp','candidate.o','-o','test'])
        marker = 'C++ self-alias and bounds: 98020 cases PASS'
    elif task == 'posix_write':
        step('compile_candidate',['gcc',*c,*san,'-Dwrite=test_write','-c',source,'-o','mock.o'])
        step('compile_candidate',['gcc',*c,*san,'-Dwrite_all_nb=real_write_all_nb','-c',source,'-o','real.o'])
        step('link_tests',['gcc',*c,*san,'/suite/posix_write_test.c','mock.o','real.o','-o','test'])
        marker = 'POSIX partial writes/EINTR/EAGAIN/zero/error + real nonblocking pipe PASS'
    elif task == 'rust_prefix':
        rust = ['--edition=2021','-F','unsafe-code','-C','opt-level=2','-C','overflow-checks=yes']
        step('compile_candidate',['rustc',*rust,'--crate-type=lib',source,'-o','candidate.rlib'])
        # Existing fixture includes this fixed path. This is only container tmpfs.
        Path('/work/rust_prefix.rs').write_bytes(Path(source).read_bytes())
        step('link_tests',['rustc',*rust,'--test','/suite/rust_prefix_test.rs','-o','test'])
        marker = 'test result: ok. 2 passed; 0 failed;'
    else:
        macro, symbol = {'aarch64_sum':('TEST_SUM','sum_u32'),
                         'neon_sad':('TEST_SAD','sad_u8_neon'),
                         'neon_dot':('TEST_DOT','dot_i8_neon')}[task]
        arm = ['-static','-std=c11','-O2','-march=armv8-a','-Wall','-Wextra','-Werror']
        step('compile_candidate',['aarch64-linux-gnu-gcc',*arm,'-D'+macro,'-c',source,'-o','candidate.o'])
        extra = ['/suite/aapcs_check.S'] if task=='aarch64_sum' else []
        step('link_tests',['aarch64-linux-gnu-gcc',*arm,'-D'+macro,'-I/suite',
                           'candidate.o',*extra,'/suite/arm_test.c','-o','test'])
        dis = step('inspect_instructions',['aarch64-linux-gnu-objdump','-d','--disassemble='+symbol,'test'])
        vector = bool(re.search(r'\bv\d+\.',dis))
        if (task=='aarch64_sum' and vector) or (task!='aarch64_sum' and not vector):
            raise Failure('ISA constraint failed')
        marker = 'AArch64 independent scalar reference + protected tails: 804 cases PASS'
    command = ['qemu-aarch64','-cpu','cortex-a53','./test'] if task in ['aarch64_sum','neon_sad','neon_dot'] else ['./test']
    output = step('execute_tests',command)
    if marker not in output:
        raise Failure('Verifier completion marker missing')
    result = {'status':'PASS','failure':None}
except Failure as error:
    result = {'status':'FAIL','failure':str(error)}
print(json.dumps({**result,'task':task,'steps':steps}),flush=True)
