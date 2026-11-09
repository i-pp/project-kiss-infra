/*
 * KISS Open License Version 1.0 (KOL-v1)
 *
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 *
 * Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
 * Contributors may add copyright notices for their own original modifications.
 * Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
 *
 * Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
 * without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
 *
 * Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
 * KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
 *
 * THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
 *
 * This header is a summary, not a separate license or an amendment to KOL-v1.
 * All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.
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
