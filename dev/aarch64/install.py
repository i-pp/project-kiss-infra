# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Image build only: pinned packages and matching official Rust compiler/target."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
import urllib.request

config = json.loads(Path('/tmp/kiss-build/versions.lock.json').read_text())
record = Path('/opt/kiss-aarch64')
record.mkdir()
snapshot = config['ubuntu_snapshot']
# Parent has no CA store. Bootstrap ONLY standard Ubuntu Mozilla roots from a
# SHA256-pinned .deb fetched over verified HTTPS by the host driver. No custom
# trust roots, HTTP fallback, or TLS/signature bypass is used.
ca_deb = Path('/tmp/kiss-build/ca-certificates.deb')
assert hashlib.sha256(ca_deb.read_bytes()).hexdigest() == config['ca_bootstrap_sha256']
subprocess.run(['dpkg-deb', '-x', str(ca_deb), '/tmp/kiss-build/ca'], check=True)
ca_bundle = Path('/tmp/kiss-build/ubuntu-mozilla.crt')
ca_bundle.write_bytes(b''.join(p.read_bytes() for p in sorted(
    Path('/tmp/kiss-build/ca/usr/share/ca-certificates').rglob('*.crt'))))
assert ca_bundle.stat().st_size > 100000
apt_tls = ['-o', f'Acquire::https::CaInfo={ca_bundle}']
# These changes are inside the NEW image only. Apt signature validation stays enabled.
Path('/etc/apt/sources.list.d/ubuntu.sources').write_text(
    'Types: deb\n'
    f'URIs: https://snapshot.ubuntu.com/ubuntu/{snapshot}/\n'
    'Suites: resolute resolute-updates resolute-security\n'
    'Components: main universe\n'
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
subprocess.run(['apt-get', *apt_tls, '-o', 'APT::Update::Error-Mode=any', 'update'], check=True)
packages = [f'{name}={version}' for name, version in config['packages'].items()]
base = ['apt-get', *apt_tls, '--yes', '--no-install-recommends', 'install']
uris = subprocess.check_output(base + ['--print-uris'] + packages, text=True)
(record / 'package-uris.txt').write_text(uris)
size = sum(int(m) for m in re.findall(r"^'[^']+'\s+\S+\s+(\d+)\s+", uris, re.MULTILINE))
print(f'APT download bytes: {size}', flush=True)
if not 0 < size <= config['apt_download_limit_bytes']:
    raise SystemExit('Unexpected APT download size: stop without changing constraints')
subprocess.run(base + packages, check=True, env=os.environ | {'DEBIAN_FRONTEND': 'noninteractive'})

def download(url, limit):
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise SystemExit('Download exceeded limit')
    return data

manifest = download(f"https://static.rust-lang.org/dist/channel-rust-{config['rust']}.toml", 2*1024**2)
assert hashlib.sha256(manifest).hexdigest() == config['rust_manifest_sha256']
rust = tomllib.loads(manifest.decode())
target = rust['pkg']['rust-std']['target'][config['rust_target']]
assert target['available'] and target['xz_hash'] == config['rust_target_sha256']
# HEAD compressed component sizes before letting rustup acquire its fixed minimal toolchain.
rust_bytes = 0
for name, arch in [('rustc', 'x86_64-unknown-linux-gnu'), ('cargo', 'x86_64-unknown-linux-gnu'),
                   ('rust-std', 'x86_64-unknown-linux-gnu'), ('rust-std', config['rust_target'])]:
    component = rust['pkg'][name]['target'][arch]
    with urllib.request.urlopen(urllib.request.Request(component['xz_url'], method='HEAD'), timeout=60) as r:
        length = int(r.headers['Content-Length'])
    rust_bytes += length
print(f'Rust compressed component bytes: {rust_bytes}', flush=True)
if not 0 < rust_bytes <= config['rust_download_limit_bytes']:
    raise SystemExit('Unexpected Rust download size')
installer = download(f"https://static.rust-lang.org/rustup/archive/{config['rustup']}/x86_64-unknown-linux-gnu/rustup-init", 32*1024**2)
assert hashlib.sha256(installer).hexdigest() == config['rustup_init_sha256']
path = Path('/tmp/kiss-build/rustup-init')
path.write_bytes(installer)
path.chmod(0o755)
env = os.environ | {'RUSTUP_HOME': '/opt/rustup', 'CARGO_HOME': '/opt/cargo',
                    'RUSTUP_INIT_SKIP_PATH_CHECK': 'yes'}
subprocess.run([str(path), '-y', '--no-modify-path', '--profile', 'minimal',
                '--default-toolchain', config['rust'], '--target', config['rust_target']],
               env=env, check=True)
# Stable command aliases and explicit LLVM_DIR prevent unversioned tools choosing LLVM 22.
aliases = Path('/opt/llvm21/bin')
aliases.mkdir(parents=True)
for name in ['clang', 'clang++', 'clang-cpp', 'ld.lld', 'lld', 'llc', 'opt', 'llvm-config',
             'llvm-as', 'llvm-dis', 'llvm-ar', 'llvm-nm', 'llvm-ranlib', 'llvm-objdump',
             'llvm-objcopy', 'llvm-readelf', 'FileCheck']:
    target = Path('/usr/bin') / (name + '-21')
    assert target.exists(), target
    (aliases / name).symlink_to(target)
all_packages = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'], text=True)
if re.search(r'^(?:clang|llvm|lld|libllvm|libclang)[^\t]*22', all_packages, re.MULTILINE):
    raise SystemExit('Unexpected LLVM 22 package: stop')
(record / 'packages.tsv').write_text(all_packages)
(record / 'versions.lock.json').write_text(json.dumps(config, indent=2) + '\n')
(record / 'rust-manifest.toml').write_bytes(manifest)
(record / 'download-sizes.json').write_text(json.dumps({'apt': size, 'rust_components': rust_bytes,
                                                       'rustup': len(installer)}, indent=2) + '\n')
# Do not prune old Docker objects or host caches. Only remove transient files in this new layer.
for file in Path('/var/lib/apt/lists').iterdir():
    if file.is_file():
        file.unlink()
path.unlink()
