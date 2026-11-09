/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

/* Environment validation only. Identity-map the low 1GiB; no general runtime. */
ENTRY(_start32)
SECTIONS {
  . = 0x100000;
  __image_start = .;
  .text : { KEEP(*(.multiboot)) KEEP(*(.text.boot)) *(.text .text.*) }
  .rodata : ALIGN(16) { *(.rodata .rodata.*) }
  .data : ALIGN(16) { *(.data .data.*) }
  __load_end = .;
  .bss (NOLOAD) : ALIGN(4096) {
    __bss_start = .; *(.bss.boot_tables) *(.bss .bss.*) *(COMMON)
    . = ALIGN(16);
  }
  .stack (NOLOAD) : { . += 0x10000; __stack_top = .; }
  __image_end = .;
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(__image_end < 0x40000000, "Validation image must fit identity mapping")
ASSERT((__stack_top & 15) == 0, "SP16")
