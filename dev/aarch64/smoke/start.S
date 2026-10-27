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
