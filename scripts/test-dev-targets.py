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

"""Bounded probes inside the networkless container, not a compiler framework."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import resource
import selectors
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time

LOG = Path(sys.argv[1])
WORK = Path('/work')/LOG.parent.parent.name/LOG.parent.name/LOG.name
WORK.mkdir(parents=True, exist_ok=False)
Path('/tmp/home').mkdir(exist_ok=True)
COMMON = Path('/src/dev/common')
X86 = Path('/src/dev/x86_64/smoke')
ARM = Path('/src/dev/aarch64/smoke')
START = time.monotonic()
COMMANDS = []
RESULTS = {}
LIMIT = 1024*1024


def command(argv, label, *, timeout=60, marker=None):
    begin = time.monotonic()
    process = subprocess.Popen([str(x) for x in argv], cwd=WORK, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True)
    output = bytearray()
    reason = None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while True:
            if time.monotonic()-begin > timeout:
                reason = 'timeout'; break
            for key,_ in selector.select(0.1):
                block = os.read(key.fileobj.fileno(),65536)
                if block: output.extend(block)
                else: selector.unregister(key.fileobj)
            if len(output)>LIMIT:
                del output[LIMIT:]; reason='output_limit'; break
            if marker and marker.encode() in output:
                reason='marker'; break
            if process.poll() is not None and not selector.get_map(): break
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL)
        process.wait()
        process.stdout.close()
    text = output.decode(errors='replace')
    (LOG/(label+'.txt')).write_text(text)
    rec = {'argv':[str(x) for x in argv], 'cwd':str(WORK), 'returncode':process.returncode,
           'stop_reason':reason, 'seconds':round(time.monotonic()-begin,3), 'log':label+'.txt'}
    COMMANDS.append(rec)
    assert (reason=='marker') if marker else (reason is None and process.returncode==0), rec
    return text


def case(name, function):
    begin = time.monotonic()
    try:
        detail = function()
        RESULTS[name]={'status':'PASS','detail':detail}
    except Exception as error:
        RESULTS[name]={'status':'FAIL','detail':repr(error)}
    RESULTS[name]['seconds']=round(time.monotonic()-begin,3)
    print(name+': '+RESULTS[name]['status'],flush=True)
    return RESULTS[name]['status']=='PASS'


def skip(name, reason):
    RESULTS[name]={'status':'SKIP','reason':reason,'seconds':0}


def isolation():
    assert os.getuid()!=0
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert int(status['CapEff'],16)==0 and status['NoNewPrivs'].strip()=='1' and status['Seccomp'].strip()=='2'
    assert sorted(p.name for p in Path('/sys/class/net').iterdir())==['lo']
    assert not any(Path(p).exists() for p in ['/dev/kfd','/dev/dri','/dev/kvm','/var/run/docker.sock'])
    for p in ['/','/src/dev/common','/src/dev/x86_64','/src/dev/aarch64']:
        assert os.statvfs(p).f_flag & os.ST_RDONLY
    cg=Path('/sys/fs/cgroup')
    limits={p:(cg/p).read_text().strip() for p in ['memory.max','memory.swap.max','pids.max','cpu.max']}
    assert limits['memory.max']=='4294967296' and limits['memory.swap.max']=='0' and limits['pids.max']=='256'
    quota,period=map(int,limits['cpu.max'].split());assert quota/period==2
    assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0)
    assert resource.getrlimit(resource.RLIMIT_FSIZE)==(134217728,134217728)
    apparmor=Path('/proc/self/attr/current').read_text().strip()
    assert apparmor.startswith('docker-default') and 'enforce' in apparmor
    with socket.socket() as s:
        s.settimeout(0.2)
        unreachable=s.connect_ex(('192.0.2.1',9))
    assert unreachable!=0
    return {'uid':os.getuid(),'gid':os.getgid(),'cap_eff':0,'no_new_privs':1,'seccomp':2,
            'apparmor':apparmor,'network_interfaces':['lo'],'external_connect_errno':unreachable,
            'limits':limits,'gpu_kvm_docker_socket':False,'read_only_root_and_sources':True}


def versions():
    versions={}
    for tool in ['clang-21','clang++-21','llvm-config-21','ld.lld-21','llvm-objdump-21',
                 'qemu-system-x86_64','qemu-system-aarch64','gdb-multiarch','cmake','ninja','python3']:
        text=command([tool,'--version'],'version-'+tool)
        versions[tool]=text.splitlines()[0]
        if tool in ['clang-21','clang++-21','llvm-config-21','ld.lld-21','llvm-objdump-21']:
            assert '21.1.8' in text
    targets=command(['llvm-config-21','--targets-built'],'llvm-targets')
    assert 'AArch64' in targets.split() and 'X86' in targets.split()
    assert os.environ['LLVM_DIR']=='/usr/lib/llvm-21/lib/cmake/llvm'
    packages=Path('/opt/kiss-x86/packages.tsv').read_text()
    assert not re.search(r'^(?:clang|llvm|lld|libllvm|libclang)[^\t]*22',packages,re.M)
    for f in ['versions.lock.json','packages.tsv','package-uris.txt','download-bytes.json']:
        shutil.copyfile('/opt/kiss-x86/'+f,LOG/f)
    return versions


def api():
    command(['cmake','-S',COMMON,'-B',WORK/'llvm-api','-G','Ninja',
             '-DCMAKE_C_COMPILER=/usr/bin/clang-21','-DCMAKE_CXX_COMPILER=/usr/bin/clang++-21',
             '-DCMAKE_BUILD_TYPE=Release'],'api-cmake-configure')
    command(['cmake','--build',WORK/'llvm-api','--parallel','2','--verbose'],'api-cmake-build',timeout=120)
    for arch,machine in [('x86_64',62),('aarch64',183)]:
        command([WORK/'llvm-api/llvm-api-smoke',arch,WORK/(arch+'-api.o'),WORK/(arch+'-api.ll')],'api-emit-'+arch)
        data=(WORK/(arch+'-api.o')).read_bytes()
        assert struct.unpack_from('<H',data,18)[0]==machine
        command(['llvm-readelf-21','-h',WORK/(arch+'-api.o')],'api-elf-'+arch)
        command(['llvm-objdump-21','-d',WORK/(arch+'-api.o')],'api-disassembly-'+arch)
    return {'llvm':'21.1.8','common_ir':'i64 add without nsw/nuw (modulo 2^64)',
            'targets':['x86_64-unknown-linux-gnu','aarch64-none-elf'],
            'target_dependent':['triple','CPU/features','data layout','target machine emission'],
            'objects':[str(WORK/'x86_64-api.o'),str(WORK/'aarch64-api.o')]}


BASE=['clang-21','-march=x86-64','-mno-avx','-mno-red-zone','-fno-pie','-fno-pic',
      '-fno-stack-protector','-ffreestanding','-O2','-g','-Wall','-Wextra','-Werror']
OBJECTS={}


def build_x86():
    for source,name,extra in [(COMMON/'api-check.c','api-check',[]),
        (COMMON/'reference.c','reference',['-fno-vectorize','-fno-slp-vectorize']),
        (X86/'probe.c','probe',[]),(X86/'simd-check.c','simd-check',[]),(X86/'native.c','native',[]),
        (X86/'bare.c','bare',[]),(X86/'serial.c','serial',[])]:
        obj=WORK/(name+'.o');OBJECTS[name]=obj
        command(BASE+extra+['-I',X86,'-c',source,'-o',obj],'compile-'+name)
    for name,bits,flags in [('sse2',128,['-msse2']),('avx2',256,['-mavx2']),('avx512',512,['-mavx512f'])]:
        obj=WORK/(name+'.o');OBJECTS[name]=obj
        command(BASE+flags+['-DSIMD_BITS='+str(bits),'-c',X86/'simd.c','-o',obj],'compile-'+name)
        assembly=command(['llvm-objdump-21','-d',obj],'disassembly-'+name)
        assert 'paddd' in assembly
        if bits>128: assert ('ymm' if bits==256 else 'zmm') in assembly
    common=[OBJECTS[n] for n in ['api-check','reference','probe','simd-check','sse2','avx2','avx512']]
    command(['clang-21','-fuse-ld=/usr/bin/ld.lld-21','-no-pie',OBJECTS['native'],*common,
             WORK/'x86_64-api.o','-o',WORK/'native.elf'],'link-native')
    command(['llvm-readelf-21','-h','-l',WORK/'native.elf'],'native-elf')
    command(['clang-21','--target=x86_64-none-elf','-c','-g',X86/'start.S','-o',WORK/'start.o'],'compile-boot')
    command(['ld.lld-21','-T',X86/'link.ld','--build-id=none',WORK/'start.o',OBJECTS['bare'],OBJECTS['serial'],
             *common,WORK/'x86_64-api.o','-o',WORK/'kernel.elf'],'link-multiboot')
    command(['llvm-readelf-21','-h','-l',WORK/'kernel.elf'],'multiboot-elf')
    command(['llvm-objdump-21','-d',WORK/'kernel.elf'],'multiboot-disassembly')
    command(['llvm-objcopy-21','-O','binary',WORK/'kernel.elf',WORK/'kernel.bin'],'multiboot-flat-image')
    image=(WORK/'kernel.bin').read_bytes()
    magic,flags,checksum,header,load,end,bss,entry=struct.unpack_from('<8I',image)
    assert magic==0x1badb002 and flags==0x10003 and (magic+flags+checksum)&0xffffffff==0
    assert load==0x100000 and end-load==len(image) and load<=entry<end<bss<0x40000000
    return {'native_elf':str(WORK/'native.elf'),'qemu_elf_symbols':str(WORK/'kernel.elf'),
            'qemu_image':str(WORK/'kernel.bin'),'multiboot_entry':hex(entry),'load':hex(load)}


def simd_results(text, mode):
    probe=json.loads(next(line[9:] for line in text.splitlines() if line.startswith('FEATURES ')))
    assert 'FAIL' not in text and 'LLVM_API_EXEC PASS' in text
    for name,key,raw,mask in [('SSE2','sse2','sse2',0),('AVX2','avx2_usable','avx2',6),
                              ('AVX512F','avx512_usable','avx512f',0xe6)]:
        result_name=mode+'_'+name.lower()
        if probe[key]:
            assert name+' PASS cases=3096' in text
            if mask:
                assert probe['xsave'] and probe['osxsave'] and probe['avx'] and probe['xcr0']&mask==mask
            RESULTS[result_name]={'status':'PASS','cases':3096,'instruction_execution':True,
                'feature_probe':probe,'detail':'Exact scalar comparison, tails and canaries; vector instructions verified in disassembly'}
        else:
            assert name+' SKIP' in text
            missing=[]
            if not probe[raw]: missing.append('CPUID '+raw+' absent')
            if not probe['xsave']: missing.append('CPUID XSAVE absent')
            if not probe['osxsave']: missing.append('OSXSAVE absent')
            if mask and probe['xcr0']&mask!=mask: missing.append('XCR0 state mask '+hex(mask)+' unavailable')
            skip(result_name,'; '.join(missing))
    return {'feature_probe':probe,'api_execution':'PASS','environment':mode}


def native():
    return simd_results(command([WORK/'native.elf'],'native-execution',timeout=30),'native')


QEMU=['qemu-system-x86_64','-machine','pc-i440fx-10.2','-cpu','qemu64','-accel','tcg',
      '-smp','1','-m','128M','-nodefaults','-display','none','-monitor','none','-nic','none','-no-reboot']


def qemu():
    machines=command(['qemu-system-x86_64','-machine','help'],'x86-qemu-machines')
    cpus=command(['qemu-system-x86_64','-cpu','help'],'x86-qemu-cpus')
    accels=command(['qemu-system-x86_64','-accel','help'],'x86-qemu-accelerators')
    assert 'pc-i440fx-10.2' in machines and 'qemu64' in cpus and 'tcg' in accels
    text=command(QEMU+['-serial','stdio','-kernel',WORK/'kernel.bin'],'x86-qemu-uart',timeout=30,marker='X86 SMOKE DONE')
    assert 'BOOT64 PASS BSS DATA SP16' in text
    return simd_results(text,'qemu') | {'machine':'pc-i440fx-10.2','cpu':'qemu64','accel':'tcg','guest_ram_mib':128}


def gdb():
    unix=Path('/tmp')/('kiss-x86-gdb-'+str(os.getpid())+'.sock')
    with (LOG/'x86-gdb-uart.txt').open('x') as out:
        p=subprocess.Popen(QEMU+['-serial','stdio','-kernel',str(WORK/'kernel.bin'),'-chardev',
            f'socket,path={unix},server=on,wait=off,id=gdb0','-gdb','chardev:gdb0','-S'],
            stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            deadline=time.monotonic()+5
            while not unix.exists() and p.poll() is None and time.monotonic()<deadline: time.sleep(0.05)
            assert unix.exists()
            script=WORK/'x86.gdb'
            script.write_text(f'''set pagination off
set confirm off
set auto-load off
set remotetimeout 5
file {WORK}/kernel.elf
target remote {unix}
info registers rip
break _start64
continue
python
assert int(gdb.parse_and_eval('$rip')) == int(gdb.parse_and_eval('&_start64'))
assert int(gdb.parse_and_eval('$cr0')) & (1 << 31)
assert int(gdb.parse_and_eval('$cr4')) & (1 << 5)
end
break debug_ready
continue
info registers rip rsp rax cr0 cr3 cr4
x/gx &debug_word
python
assert int(gdb.parse_and_eval('debug_word')) == 0x1122334455667788
assert int(gdb.parse_and_eval('debug_bss')) == 0
assert int(gdb.parse_and_eval('boot_rsp')) % 16 == 0
end
set $before_step = $rip
stepi
python
assert int(gdb.parse_and_eval('$rip')) != int(gdb.parse_and_eval('$before_step'))
end
break validation_done
continue
x/gx &debug_results
python
assert int(gdb.parse_and_eval('debug_results')) == 0x50415353
end
echo GDB PASS x86 long mode registers memory step\\n
detach
quit
''')
            text=command(['gdb-multiarch','-nx','-nh','--batch','-x',script],'x86-gdb',timeout=30)
            assert 'GDB PASS' in text
        finally:
            if p.poll() is None: os.killpg(p.pid,signal.SIGTERM)
            try: p.wait(timeout=2)
            except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL);p.wait()
            unix.unlink(missing_ok=True)
    assert (LOG/'x86-gdb-uart.txt').stat().st_size<=LIMIT
    return 'UNIX socket: reset stop, long-mode entry, breakpoints, registers, known memory, single-step'


def aarch64():
    arm=WORK/'arm';arm.mkdir()
    machine='virt-10.2,secure=off,virtualization=off'
    args=['qemu-system-aarch64','-machine',machine,'-cpu','cortex-a53','-accel','tcg','-smp','1',
          '-m','256M','-nodefaults','-display','none','-monitor','none','-nic','none']
    dump=args.copy();dump[2]+= ',dumpdtb='+str(arm/'virt.dtb')
    command(dump,'arm-api-dump-dtb')
    command(['dtc','-I','dtb','-O','dts','-o',arm/'virt.dts',arm/'virt.dtb'],'arm-api-dtc')
    dts=(arm/'virt.dts').read_text()
    assert re.search(r'memory@40000000\s*\{[^{}]*reg = <0x00 0x40000000 0x00 0x10000000>',dts)
    assert re.search(r'pl011@9000000\s*\{[^{}]*reg = <0x00 0x9000000 0x00 0x1000>',dts)
    (arm/'uart_config.h').write_text('#define UART_BASE UINT64_C(0x09000000)\n')
    (arm/'link.ld').write_text((ARM/'link.ld.in').read_text().replace('@ORIGIN@','0x40200000').replace('@LENGTH@','0xfe00000'))
    objects=[]
    for source,label in [(ARM/'start.S','start'),(ARM/'uart.c','uart'),(COMMON/'aarch64-api.c','main'),(COMMON/'api-check.c','check')]:
        obj=arm/(label+'.o');objects.append(obj)
        command(['clang-21','--target=aarch64-none-elf','-mcpu=cortex-a53','-mstrict-align','-ffreestanding',
                 '-fno-stack-protector','-fno-pic','-O2','-g','-I',arm,'-I',ARM,'-c',source,'-o',obj],'arm-api-compile-'+label)
    command(['ld.lld-21','-T',arm/'link.ld',*objects,WORK/'aarch64-api.o','-o',arm/'api.elf'],'arm-api-link')
    command(['llvm-readelf-21','-h','-l',arm/'api.elf'],'arm-api-elf')
    command(['llvm-objdump-21','-d',arm/'api.elf'],'arm-api-disassembly')
    text=command(args+['-serial','stdio','-kernel',arm/'api.elf'],'arm-api-uart',timeout=30,marker='AARCH64 API DONE')
    assert 'LLVM_API_EXEC PASS aarch64' in text and 'FAIL' not in text
    return {'common_cases':5,'execution':'qemu-system-aarch64','linker':'LLD 21.1.8','existing_startup_uart':'reused read-only'}


try:
    if case('effective_isolation',isolation) and case('tool_versions',versions) and case('llvm_cpp_api',api):
        if case('x86_elf_build',build_x86):
            case('x86_native',native)
            if case('x86_qemu_multiboot',qemu): case('x86_gdb',gdb)
            else: skip('x86_gdb','QEMU boot failed; see preserved UART/command logs')
        else:
            for name in ['x86_native','x86_qemu_multiboot','x86_gdb']: skip(name,'x86 build failed')
        case('aarch64_api_execution',aarch64)
    else:
        for name in ['x86_elf_build','x86_native','x86_qemu_multiboot','x86_gdb','aarch64_api_execution']:
            skip(name,'Isolation, toolchain or common LLVM API prerequisite failed')
finally:
    report={'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'results':RESULTS,'commands':COMMANDS,
            'seconds':round(time.monotonic()-START,3),'work':str(WORK),
            'memory_peak_bytes':int(Path('/sys/fs/cgroup/memory.peak').read_text()),
            'artifact_file_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file())}
    (LOG/'report.json').write_text(json.dumps(report,indent=2)+'\n')
sys.exit(1 if any(r['status']=='FAIL' for r in RESULTS.values()) else 0)
