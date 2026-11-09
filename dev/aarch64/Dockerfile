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

# Parent is LOCAL. scripts/dev-aarch64.py checks its full immutable ID before build.
FROM project-kiss-code-eval:20261027

COPY versions.lock.json install.py /tmp/kiss-build/
COPY .cache/ca-certificates.deb /tmp/kiss-build/ca-certificates.deb
RUN python3 /tmp/kiss-build/install.py

# No implicit LLVM selection. Rust links with system LLD 21, not its bundled linker.
ENV PATH="/opt/llvm21/bin:/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    CC=/usr/bin/clang-21 CXX=/usr/bin/clang++-21 LD=/usr/bin/ld.lld-21 \
    AR=/usr/bin/llvm-ar-21 NM=/usr/bin/llvm-nm-21 RANLIB=/usr/bin/llvm-ranlib-21 \
    OBJDUMP=/usr/bin/llvm-objdump-21 OBJCOPY=/usr/bin/llvm-objcopy-21 \
    LLVM_DIR=/usr/lib/llvm-21/lib/cmake/llvm \
    CARGO_HOME=/opt/cargo RUSTUP_HOME=/opt/rustup RUSTUP_TOOLCHAIN=1.93.1 \
    CARGO_TARGET_AARCH64_UNKNOWN_NONE_LINKER=/usr/bin/ld.lld-21 \
    CARGO_NET_OFFLINE=true HOME=/tmp/home
WORKDIR /work
USER 65534:65534
CMD ["bash"]
