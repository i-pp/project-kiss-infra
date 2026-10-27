"""Run only inside the isolated evaluation container. Never repair model output."""
import json
import os
from pathlib import Path
import re
import subprocess

os.chdir('/work')
if Path('test-results.json').exists(): raise SystemExit('Preserve existing test-results.json first')
os.environ['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
suite=Path('/suite')
results={}
commands=[]

def run(args, timeout=60):
    p=subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    commands.append({'argv':args,'returncode':p.returncode,'output':p.stdout})
    if p.returncode: raise RuntimeError(p.stdout[-12000:])
    return p.stdout

versions={c:run([c,'--version']).splitlines()[0] for c in ['gcc','g++','rustc','aarch64-linux-gnu-gcc','qemu-aarch64']}
cflags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-D_POSIX_C_SOURCE=200809L']
san=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']

def test_c_parse():
    run(['gcc',*cflags,*san,'-c','c_parse.c','-o','c_parse.o'])
    run(['g++','-std=c++20','-O2',*san,str(suite/'c_parse_test.cpp'),'c_parse.o','-o','c_parse_test'])
    return run(['./c_parse_test'])

def test_cpp_alias():
    run(['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror','-D_GLIBCXX_DEBUG',*san,'cpp_alias.cpp',str(suite/'cpp_alias_test.cpp'),'-o','cpp_alias_test'])
    return run(['./cpp_alias_test'])

def test_posix():
    run(['gcc',*cflags,*san,'-Dwrite=test_write','-c','posix_write.c','-o','posix_mock.o'])
    run(['gcc',*cflags,*san,'-Dwrite_all_nb=real_write_all_nb','-c','posix_write.c','-o','posix_real.o'])
    run(['gcc',*cflags,*san,str(suite/'posix_write_test.c'),'posix_mock.o','posix_real.o','-o','posix_test'])
    return run(['./posix_test'])

def test_rust():
    run(['rustc','--edition=2021','-F','unsafe-code','-C','opt-level=2','-C','overflow-checks=yes','--test',str(suite/'rust_prefix_test.rs'),'-o','rust_test'])
    return run(['./rust_test'])

def test_arm(name, macro):
    extra=[str(suite/'aapcs_check.S')] if macro=='TEST_SUM' else []
    run(['aarch64-linux-gnu-gcc','-static','-std=c11','-O2','-march=armv8-a','-Wall','-Wextra','-Werror','-D'+macro,'-I/suite',name,*extra,str(suite/'arm_test.c'),'-o',macro])
    symbol={'TEST_SUM':'sum_u32','TEST_SAD':'sad_u8_neon','TEST_DOT':'dot_i8_neon'}[macro]
    dis=run(['aarch64-linux-gnu-objdump','-d','--disassemble='+symbol,macro])
    Path(macro+'.disassembly.txt').write_text(dis)
    vector_instructions=bool(re.search(r'\bv\d+\.',dis))
    if macro=='TEST_SUM' and vector_instructions: raise RuntimeError('Scalar-only requirement violated')
    if macro!='TEST_SUM' and not vector_instructions: raise RuntimeError('No NEON instructions found in target function')
    return run(['qemu-aarch64','-cpu','cortex-a53','./'+macro])

tests={'c_parse':test_c_parse,'cpp_alias':test_cpp_alias,'posix_write':test_posix,'rust_prefix':test_rust,
       'aarch64_sum':lambda:test_arm('aarch64_sum.S','TEST_SUM'),
       'neon_sad':lambda:test_arm('neon_sad.c','TEST_SAD'),
       'neon_dot':lambda:test_arm('neon_dot.c','TEST_DOT')}
for name,test in tests.items():
    start=len(commands)
    try: results[name]={'status':'PASS','evidence':test()}
    except (RuntimeError,subprocess.TimeoutExpired) as error: results[name]={'status':'FAIL','evidence':str(error)}
    results[name]['commands']=commands[start:]
    print(name,results[name]['status'],flush=True)
Path('test-results.json').write_text(json.dumps({'versions':versions,'results':results},indent=2)+'\n')
