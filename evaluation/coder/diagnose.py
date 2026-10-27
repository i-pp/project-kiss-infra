"""Supplemental diagnosis only; do not change original sources or first-pass scores."""
import json
import os
from pathlib import Path
import subprocess

os.chdir('/work')
if Path('diagnostics.json').exists(): raise SystemExit('Preserve existing diagnostics.json first')
os.environ['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
records=[]
def run(args):
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
        r={'argv':args,'returncode':p.returncode,'output':p.stdout}
    except subprocess.TimeoutExpired as error:
        r={'argv':args,'returncode':'timeout','output':str(error)}
    records.append(r);return r

flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-D_POSIX_C_SOURCE=200809L']
san=['-fsanitize=address,undefined','-fno-sanitize-recover=all']
run(['gcc',*flags,*san,'-include','stddef.h','-c','c_parse.c','-o','diag_parse.o'])
run(['g++','-std=c++20','-O2',*san,'/suite/c_parse_test.cpp','diag_parse.o','-o','diag_parse'])
run(['./diag_parse'])
run(['gcc',*flags,*san,'-include','limits.h','-Dwrite=test_write','-c','posix_write.c','-o','diag_posix_mock.o'])
run(['gcc',*flags,*san,'-include','limits.h','-Dwrite_all_nb=real_write_all_nb','-c','posix_write.c','-o','diag_posix_real.o'])
run(['gcc',*flags,*san,'/suite/posix_write_test.c','diag_posix_mock.o','diag_posix_real.o','-o','diag_posix'])
run(['./diag_posix'])
run(['aarch64-linux-gnu-gcc','-static',*flags,'-march=armv8-a','-include','stdlib.h','-DTEST_SAD','-I/suite','neon_sad.c','/suite/arm_test.c','-o','diag_sad'])
run(['qemu-aarch64','-cpu','cortex-a53','./diag_sad'])
Path('diag_zero.S').write_text('''.text
.global _start
_start:
mov x0,#0
mov x1,#0
mov x3,#0x1234
bl sum_u32
cmp x0,#0
cset x0,ne
mov x8,#93
svc #0
.section .note.GNU-stack,"",%progbits
''')
run(['aarch64-linux-gnu-gcc','-static','-nostdlib','-march=armv8-a','aarch64_sum.S','diag_zero.S','-o','diag_zero'])
run(['qemu-aarch64','-cpu','cortex-a53','./diag_zero'])
Path('diagnostics.json').write_text(json.dumps(records,indent=2)+'\n')
for r in records:
    print(r['argv'][-1],r['returncode'],r['output'][-1200:],flush=True)
