// KISS Open License Version 1.0 (KOL-v1)
//
// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1
//
// Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
// Contributors may add copyright notices for their own original modifications.
// Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
//
// Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
// without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
//
// Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
// KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
//
// THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
//
// This header is a summary, not a separate license or an amendment to KOL-v1.
// All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

// Environment-validation startup only; NOT an AceIS/Abiss implementation.
.section .text.boot,"ax"
.global _start
.type _start,%function
_start:
    // Configuration must enter EL1. Other ELs deliberately cannot report PASS.
    mrs x0, CurrentEL
    cmp x0, #4
    b.ne unsupported_el
    ldr x0, =__stack_top
    mov sp, x0
    ldr x0, =__bss_start
    ldr x1, =__bss_end
1:  cmp x0, x1
    b.hs 2f
    str xzr, [x0], #8
    b 1b
2:  // Enable FP/AdvSIMD before C or Rust can use the hard-float ABI.
    mrs x0, cpacr_el1
    orr x0, x0, #0x300000
    msr cpacr_el1, x0
    isb
    bl smoke_main
3:  wfi
    b 3b
unsupported_el:
    b unsupported_el
.size _start, .-_start
