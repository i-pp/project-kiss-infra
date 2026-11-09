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

"""Build the new child only. No LLVM reinstall and no host package changes."""
import json
import os
from pathlib import Path
import re
import subprocess

lock = json.loads(Path('/tmp/kiss-x86-build/versions.lock.json').read_text())
record = Path('/opt/kiss-x86')
record.mkdir()
sources = Path('/etc/apt/sources.list.d/ubuntu.sources').read_text()
assert f"https://snapshot.ubuntu.com/ubuntu/{lock['ubuntu_snapshot']}/" in sources
subprocess.run(['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'], check=True)
packages = [f'{k}={v}' for k, v in lock['packages'].items()]
base = ['apt-get', '--yes', '--no-install-recommends', '--no-upgrade', 'install']
uris = subprocess.check_output(base+['--print-uris']+packages, text=True)
size = sum(map(int, re.findall(r"^'[^']+'\s+\S+\s+(\d+)\s+", uris, re.MULTILINE)))
print(f'Additional package download bytes: {size}', flush=True)
assert 0 < size <= lock['download_limit_bytes'], 'Unexpected dependency download size'
(record/'package-uris.txt').write_text(uris)
subprocess.run(base+packages, env=os.environ | {'DEBIAN_FRONTEND': 'noninteractive'}, check=True)
versions = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'], text=True)
assert not re.search(r'^(?:clang|llvm|lld|libllvm|libclang)[^\t]*22', versions, re.MULTILINE)
for command in ['clang-21', 'ld.lld-21', 'llvm-config-21']:
    output = subprocess.check_output([command, '--version'], text=True)
    assert lock['llvm'] in output
(record/'packages.tsv').write_text(versions)
(record/'versions.lock.json').write_text(json.dumps(lock, indent=2)+'\n')
(record/'download-bytes.json').write_text(json.dumps({'apt_download_bytes': size})+'\n')
for p in Path('/var/lib/apt/lists').iterdir():
    if p.is_file():
        p.unlink()  # Only transient indexes in the NEW image layer.
