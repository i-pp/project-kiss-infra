#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Run ONLY in the networkless development container. Standard library only."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import time

SOURCE = Path('/src/dev/aarch64')
LOG = Path(sys.argv[1])
WORK = Path('/work') / LOG.parent.name / LOG.name
WORK.mkdir(parents=True, exist_ok=False)
(Path('/tmp/home')).mkdir(exist_ok=True)
COMMANDS = []
RESULTS = {}
START = time.monotonic()
OUTPUT_LIMIT = 1024 * 1024


def command(argv, label, *, timeout=60, cwd=WORK, env=None, marker=None):
    begin = time.monotonic()
    process = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    output = bytearray()
    reason = None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while True:
            if time.monotonic() - begin > timeout:
                reason = 'timeout'; break
            events = selector.select(0.1)
            for key, _ in events:
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(block)
            if len(output) > OUTPUT_LIMIT:
                output = output[:OUTPUT_LIMIT]; reason = 'output_limit'; break
            if marker and marker.encode() in output:
                reason = 'marker'; break
            if process.poll() is not None and not selector.get_map():
                break
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        process.stdout.close()
    text = output.decode(errors='replace')
    (LOG / (label + '.txt')).write_text(text)
    rec = {'argv': [str(x) for x in argv], 'cwd': str(cwd), 'returncode': process.returncode,
           'stop_reason': reason, 'seconds': round(time.monotonic()-begin, 3),
           'log': label+'.txt', 'bytes': len(output)}
    COMMANDS.append(rec)
    if marker:
        assert reason == 'marker', rec
    else:
        assert process.returncode == 0 and reason is None, rec
    return text


def case(name, function):
    try:
        detail = function()
        RESULTS[name] = {'status': 'PASS', 'detail': detail}
    except Exception as error:
        RESULTS[name] = {'status': 'FAIL', 'detail': str(error)}
    print(name + ': ' + RESULTS[name]['status'], flush=True)
    return RESULTS[name]['status'] == 'PASS'


def skip(names, dependency):
    for name in names:
        RESULTS[name] = {'status': 'SKIP', 'detail': 'Prerequisite failed: ' + dependency}


def isolation():
    assert os.geteuid() != 0
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert int(status['CapEff'].strip(), 16) == 0
    assert status['NoNewPrivs'].strip() == '1'
    assert status['Seccomp'].strip() == '2'
    assert sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo']
    assert not any(Path(x).exists() for x in ['/dev/kfd', '/dev/dri', '/dev/kvm', '/var/run/docker.sock'])
    for path in ['/', '/src/dev/aarch64']:
        assert os.statvfs(path).f_flag & os.ST_RDONLY
    cg = Path('/sys/fs/cgroup')
    limits = {f: (cg/f).read_text().strip() for f in ['memory.max', 'memory.swap.max', 'pids.max', 'cpu.max']}
    assert limits['memory.max'] == '4294967296'
    assert limits['memory.swap.max'] == '0'
    assert limits['pids.max'] == '256'
    quota, period = map(int, limits['cpu.max'].split())
    assert quota / period == 2
    return {'uid': os.getuid(), 'limits': limits, 'network': 'lo only', 'cap_eff': 0,
            'seccomp': 2, 'no_new_privs': 1, 'gpu': False, 'source_read_only': True}


def versions():
    tools = {'clang': ['clang', '--version'], 'clang++': ['clang++', '--version'],
             'llc': ['llc', '--version'], 'llvm-config': ['llvm-config', '--version'],
             'lld': ['ld.lld', '--version'], 'llvm-objdump': ['llvm-objdump', '--version'],
             'FileCheck': ['FileCheck', '--version'], 'rustc': ['rustc', '-vV'],
             'cargo': ['cargo', '--version'], 'rustup': ['rustup', '--version'],
             'qemu-system-aarch64': ['qemu-system-aarch64', '--version'],
             'gdb-multiarch': ['gdb-multiarch', '--version'], 'cmake': ['cmake', '--version'],
             'ninja': ['ninja', '--version'], 'dtc': ['dtc', '--version'],
             'gcc': ['gcc', '--version'], 'aarch64-linux-gnu-gcc': ['aarch64-linux-gnu-gcc', '--version'],
             'qemu-aarch64': ['qemu-aarch64', '--version'], 'python3': ['python3', '--version']}
    output = {name: command(args, 'version-'+name) for name,args in tools.items()}
    for name in ['clang', 'clang++', 'llc', 'llvm-config', 'lld', 'llvm-objdump', 'FileCheck']:
        assert '21.1.8' in output[name]
        assert Path(shutil.which('ld.lld' if name == 'lld' else name)).resolve().is_relative_to('/usr/lib/llvm-21')
    assert 'rustc 1.93.1' in output['rustc']
    # Rust's internal LLVM version is recorded separately; all external compiler/linker
    # selection is explicit. No LLVM 22 package or CMake discovery is accepted.
    assert 'LLVM version: 21.1.8' in output['rustc']
    targets = command(['rustup', 'target', 'list', '--installed'], 'rust-targets')
    assert 'aarch64-unknown-none' in targets
    command(['rustc', '--print', 'target-features', '--target', 'aarch64-unknown-none'], 'rust-target-features')
    packages = Path('/opt/kiss-aarch64/packages.tsv').read_text()
    assert not re.search(r'^(?:clang|llvm|lld|libllvm|libclang)[^\t]*22', packages, re.MULTILINE)
    assert os.environ['LLVM_DIR'] == '/usr/lib/llvm-21/lib/cmake/llvm'
    for filename in ['packages.tsv', 'versions.lock.json', 'download-sizes.json', 'package-uris.txt']:
        shutil.copyfile('/opt/kiss-aarch64/'+filename, LOG/filename)
    return {name: {'version': text.splitlines()[0], 'path': shutil.which(args[0])}
            for (name, args), text in zip(tools.items(), output.values())}


MACHINE = 'virt-10.2,secure=off,virtualization=off'
QEMU = ['qemu-system-aarch64', '-machine', MACHINE, '-cpu', 'cortex-a53',
        '-accel', 'tcg', '-smp', '1', '-m', '256M', '-nodefaults',
        '-display', 'none', '-monitor', 'none', '-nic', 'none']


def capabilities():
    machines = command(['qemu-system-aarch64', '-machine', 'help'], 'qemu-machines')
    cpus = command(['qemu-system-aarch64', '-cpu', 'help'], 'qemu-cpus')
    accels = command(['qemu-system-aarch64', '-accel', 'help'], 'qemu-accelerators')
    command(['qemu-system-aarch64', '-device', 'help'], 'qemu-devices')
    command(['qemu-system-aarch64', '-machine', 'virt-10.2', '-chardev', 'help'], 'qemu-chardevs')
    props = command(['qemu-system-aarch64', '-machine', 'virt-10.2,help'], 'qemu-virt-properties')
    assert 'virt-10.2' in machines and 'cortex-a53' in cpus and 'tcg' in accels
    assert 'secure=' in props and 'virtualization=' in props
    command([
        'qemu-system-aarch64', '-machine', MACHINE+',dumpdtb='+str(WORK/'virt.dtb'),
        *QEMU[3:]], 'qemu-dump-dtb')
    command(['dtc', '-I', 'dtb', '-O', 'dts', '-o', WORK/'virt.dts', WORK/'virt.dtb'], 'dtc')
    dts = (WORK/'virt.dts').read_text()
    shutil.copyfile(WORK/'virt.dts', LOG/'virt.dts')
    # For this one fixed board, decode root 2-cell addressing explicitly and fail
    # rather than guessing if the representation or device count changes.
    assert re.search(r'#address-cells\s*=\s*<0x02>;', dts)
    assert re.search(r'#size-cells\s*=\s*<0x02>;', dts)
    uart_nodes = re.findall(r'pl011@[0-9a-f]+\s*\{([^{}]+)\}', dts)
    assert len(uart_nodes) == 1
    assert 'arm,pl011' in uart_nodes[0]
    def cells(node):
        match = re.search(r'\breg\s*=\s*<([^>]+)>;', node)
        values = [int(x,16) for x in match[1].split()]
        assert len(values) == 4
        return (values[0]<<32)|values[1], (values[2]<<32)|values[3]
    uart, uart_size = cells(uart_nodes[0])
    memory = re.findall(r'memory@[0-9a-f]+\s*\{([^{}]+)\}', dts)
    assert len(memory) == 1
    ram, size = cells(memory[0])
    assert size == 256*1024**2 and uart_size >= 0x1000
    assert (WORK/'virt.dtb').stat().st_size < 2*1024**2
    config = WORK/'config'
    config.mkdir()
    (config/'uart_config.h').write_text(f'#define UART_BASE UINT64_C(0x{uart:x})\n')
    (config/'uart_config.rs').write_text(f'const UART_BASE: usize = 0x{uart:x};\n')
    ld = (SOURCE/'smoke/link.ld.in').read_text().replace('@ORIGIN@',hex(ram+2*1024**2)).replace('@LENGTH@',hex(size-2*1024**2))
    (config/'link.ld').write_text(ld)
    return {'machine': MACHINE, 'cpu': 'cortex-a53', 'accelerator': 'tcg',
            'uart_base': hex(uart), 'ram_base': hex(ram), 'ram_bytes': size,
            'elf_origin': hex(ram+2*1024**2), 'dtb_reserved_bytes': 2*1024**2}


def build_c():
    common = ['clang-21', '--target=aarch64-none-elf', '-mcpu=cortex-a53', '-mstrict-align', '-ffreestanding']
    command(common+['-O2', '-S', '-emit-llvm', SOURCE/'smoke/simd.c', '-o', WORK/'simd.ll'], 'clang-ir')
    command(['llvm-as-21', WORK/'simd.ll', '-o', WORK/'simd.bc'], 'llvm-as')
    command(['llvm-dis-21', WORK/'simd.bc', '-o', WORK/'simd-roundtrip.ll'], 'llvm-dis')
    command(['llc-21', '-mtriple=aarch64-none-elf', '-mcpu=cortex-a53', WORK/'simd.bc', '-o', WORK/'simd.s'], 'llc-aarch64')
    check = WORK/'simd.check'
    check.write_text('; CHECK: uabd\n; CHECK: uaddlv\n; CHECK: smull\n; CHECK: saddlv\n')
    command(['FileCheck-21', check, '--input-file='+str(WORK/'simd.s')], 'filecheck-neon')
    command(['cmake', '-S', SOURCE/'smoke', '-B', WORK/'c', '-G', 'Ninja',
             '-DCMAKE_TOOLCHAIN_FILE='+str(SOURCE/'toolchain.cmake'),
             '-DVALIDATION_CONFIG='+str(WORK/'config'), '-DVALIDATION_LINKER='+str(WORK/'config/link.ld'),
             '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'], 'cmake-configure')
    command(['cmake', '--build', WORK/'c', '--verbose', '--parallel', '2'], 'cmake-build')
    elf = WORK/'c/c-smoke.elf'
    header = command(['llvm-readelf-21', '-h', '-l', elf], 'c-elf')
    disasm = command(['llvm-objdump-21', '-d', elf], 'c-disassembly')
    assert 'AArch64' in header and '0x40200000' in header
    assert all(m in disasm for m in ['uabd', 'uaddlv', 'smull', 'saddlv'])
    ir = (WORK/'simd.ll').read_text()
    assert 'aarch64' in ir
    return {'elf': str(elf), 'ir': str(WORK/'simd.ll'), 'linker': '/usr/bin/ld.lld-21'}


def boot_c():
    text = command(QEMU+['-serial', 'stdio', '-kernel', WORK/'c/c-smoke.elf'],
                   'c-uart', timeout=30, marker='SMOKE DONE')
    assert 'FAIL' not in text and 'C_ASM PASS EL1 BSS DATA SP16' in text
    return text.strip()


def neon():
    text = (LOG/'c-uart.txt').read_text()
    assert 'NEON PASS cases=4128' in text and 'FAIL' not in text
    return {'cases': 4128, 'functions': ['u8 SAD', 'i16 dot -> i64'],
            'lengths': '0..257', 'offsets': '0..3 elements', 'patterns': 4,
            'oracle': 'separate scalar TU with vectorization disabled + fixed known answers'}


def gdb():
    unix = Path('/tmp') / ('kiss-gdb-'+str(os.getpid())+'.sock')
    uart = LOG/'gdb-uart.txt'
    with uart.open('x') as output:
        process = subprocess.Popen(QEMU+['-serial', 'stdio', '-kernel', str(WORK/'c/c-smoke.elf'),
            '-chardev', f'socket,path={unix},server=on,wait=off,id=gdb0',
            '-gdb', 'chardev:gdb0', '-S'], stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            deadline = time.monotonic()+5
            while not unix.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.05)
            assert unix.exists(), 'QEMU did not create the UNIX gdb socket'
            script = WORK/'gdb.cmd'
            script.write_text(f'''set pagination off
set confirm off
set auto-load off
set remotetimeout 5
file {WORK}/c/c-smoke.elf
target remote {unix}
python
assert int(gdb.parse_and_eval('$pc')) == int(gdb.parse_and_eval('&_start'))
end
break debug_ready
continue
info registers pc sp x0 cpsr
x/gx &debug_word
python
assert int(gdb.parse_and_eval('debug_word')) == 0x1122334455667788
assert int(gdb.parse_and_eval('debug_bss')) == 0
assert int(gdb.parse_and_eval('$sp')) % 16 == 0
end
set $before_step = $pc
stepi
python
assert int(gdb.parse_and_eval('$pc')) != int(gdb.parse_and_eval('$before_step'))
end
break validation_done
continue
x/gx &debug_results
python
assert int(gdb.parse_and_eval('debug_results')) == 0x50415353
end
echo GDB PASS stop registers memory stepi breakpoints\\n
detach
quit
''')
            text = command(['gdb-multiarch', '-nx', '-nh', '--batch', '-x', script], 'gdb', timeout=30)
            assert 'GDB PASS' in text
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()
            unix.unlink(missing_ok=True)
    assert uart.stat().st_size <= OUTPUT_LIMIT
    return 'Initial stop, breakpoint stops, single step, registers and known memory checked over UNIX socket'


def diagnose_exception():
    """Evidence only, never converts a failed boot into PASS."""
    unix = Path('/tmp') / ('kiss-diagnose-'+str(os.getpid())+'.sock')
    with (LOG/'exception-uart.txt').open('x') as output:
        process = subprocess.Popen(QEMU+['-serial', 'stdio', '-kernel', str(WORK/'c/c-smoke.elf'),
            '-chardev', f'socket,path={unix},server=on,wait=off,id=gdb0',
            '-gdb', 'chardev:gdb0', '-S'], stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            deadline = time.monotonic()+5
            while not unix.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.05)
            assert unix.exists()
            script = WORK/'exception.cmd'
            script.write_text(f'''set pagination off
set confirm off
set auto-load off
file {WORK}/c/c-smoke.elf
target remote {unix}
info registers pc
break *0x0
break *0x200
break *0x400
break *0x600
continue
info all-registers
x/8i $ELR_EL1
detach
quit
''')
            command(['gdb-multiarch', '-nx', '-nh', '--batch', '-x', script], 'exception-gdb', timeout=10)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
            unix.unlink(missing_ok=True)


def rust():
    directory = WORK/'rust-src'
    shutil.copytree(SOURCE/'smoke/rust', directory)
    flags = ['-C', 'target-cpu=cortex-a53', '-C', 'linker=/usr/bin/ld.lld-21',
             '-C', 'linker-flavor=ld.lld', '-C', 'link-arg=-T'+str(WORK/'config/link.ld'),
             '-C', 'link-arg='+str(WORK/'c/CMakeFiles/c-smoke.elf.dir/start.S.obj'),
             '-C', 'link-arg=--build-id=none']
    env = os.environ | {'VALIDATION_CONFIG': str(WORK/'config'),
                         'CARGO_TARGET_DIR': str(WORK/'rust-target'), 'RUSTFLAGS': ' '.join(flags)}
    command(['cargo', 'build', '--release', '--locked', '--offline', '--target', 'aarch64-unknown-none',
             '--manifest-path', directory/'Cargo.toml', '-vv'], 'cargo-build', env=env, timeout=120)
    elf = WORK/'rust-target/aarch64-unknown-none/release/rust-smoke'
    command(['llvm-readelf-21', '-h', '-l', elf], 'rust-elf')
    command(['llvm-objdump-21', '-d', elf], 'rust-disassembly')
    text = command(QEMU+['-serial', 'stdio', '-kernel', elf], 'rust-uart', timeout=30, marker='SMOKE DONE')
    assert 'RUST PASS no_std core EL1 FP' in text and 'FAIL' not in text
    return text.strip()


try:
    if not case('isolation', isolation):
        skip(['versions', 'qemu_virt_dtb', 'c_asm_ir_elf', 'pl011_boot', 'neon', 'gdb', 'rust_no_std'], 'isolation')
    elif not case('versions', versions):
        skip(['qemu_virt_dtb', 'c_asm_ir_elf', 'pl011_boot', 'neon', 'gdb', 'rust_no_std'], 'versions')
    elif not case('qemu_virt_dtb', capabilities):
        skip(['c_asm_ir_elf', 'pl011_boot', 'neon', 'gdb', 'rust_no_std'], 'qemu_virt_dtb')
    elif not case('c_asm_ir_elf', build_c):
        skip(['pl011_boot', 'neon', 'gdb', 'rust_no_std'], 'c_asm_ir_elf')
    else:
        if case('pl011_boot', boot_c):
            case('neon', neon)
            case('gdb', gdb)
            case('rust_no_std', rust)
        else:
            try:
                diagnose_exception()
            except Exception as error:
                (LOG/'exception-diagnostic-error.txt').write_text(str(error))
            skip(['neon', 'gdb', 'rust_no_std'], 'pl011_boot')
finally:
    report = {'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'results': RESULTS,
              'commands': COMMANDS, 'seconds': round(time.monotonic()-START, 3),
              'work': str(WORK), 'source': str(SOURCE),
              'cgroup_memory_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text()),
              'artifact_bytes': sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file())}
    (LOG/'report.json').write_text(json.dumps(report, indent=2)+'\n')
sys.exit(0 if RESULTS and all(x['status']=='PASS' for x in RESULTS.values()) else 1)
