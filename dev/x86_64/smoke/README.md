# Environment validation only

The Multiboot header, protected-to-long-mode transition, identity page tables,
COM1 polling and linker layout are probes for this container/QEMU configuration.
They are **not** the AceIS/Abiss boot specification, ABI or production runtime.

Build an ELF64 using Clang/LLD 21 and convert its loadable sections to a flat
Multiboot image with explicit load/entry/BSS addresses. QEMU's Multiboot loader
does not directly accept an ELF64 x86-64 kernel through its ELF loading path.
Keep the ELF64 for disassembly and GDB symbols. No GRUB, NASM, ISO or guest OS
image is needed. Start one CPU, TCG, 128MiB, no network or host file access.

SSE2 is mandatory. AVX2 and the AVX-512F subset are gated on CPUID, OSXSAVE and
XGETBV, then require execution of the respective vector instructions and exact
agreement with a separate scalar reference. The selected QEMU CPU and guest
state are recorded independently from the native CPU/OS. No +avx feature is
forced onto an unsupported emulated CPU. The minimal guest enables SSE state
only; it is not an AVX context-switching runtime.
