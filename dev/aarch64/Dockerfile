# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

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
