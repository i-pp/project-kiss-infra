# Environment validation only

These startup, linker, UART and SIMD examples validate the development container.
They are **not** the AceIS/Abiss boot sequence, ABI, runtime, device drivers or
compiler implementation. They intentionally support only the verified QEMU
`virt-10.2` / `cortex-a53` / EL1 configuration, one CPU and no MMU/interrupts.

The test driver reads the generated DTB before generating `uart_config.h` and
the linker script. The first 2 MiB of RAM are reserved for the QEMU DTB. Guest
programs never use semihosting or access host files.

With the stage-1 MMU disabled, data memory has Device-nGnRnE attributes.
The C validation toolchain therefore uses `-mstrict-align`; it does not assume
Linux-like Normal RAM mappings. Unaligned buffer offsets remain in the tests.
This is a validation constraint, not an AceIS/Abiss memory-mapping design.
