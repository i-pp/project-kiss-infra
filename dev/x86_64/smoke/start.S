// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1

// Environment validation ONLY. NOT the AceIS/Abiss boot specification.
// QEMU Multiboot enters in 32-bit protected mode; this probe switches to long mode.
.section .multiboot,"a"
.p2align 2
mb_header:
    .long 0x1badb002
    .long 0x00010003
    .long -(0x1badb002+0x00010003)
    .long mb_header
    .long __image_start
    .long __load_end
    .long __image_end
    .long _start32

.section .text.boot,"ax"
.code32
.global _start32
_start32:
    cli
    cld
    movl $__stack_top,%esp
    xorl %eax,%eax
    movl $__bss_start,%edi
    movl $__image_end,%ecx
    subl %edi,%ecx
    shrl $2,%ecx
    rep stosl
    movl $page_pdpt,%eax
    orl $3,%eax
    movl %eax,page_pml4
    movl $page_pd,%eax
    orl $3,%eax
    movl %eax,page_pdpt
    movl $page_pd,%edi
    movl $0x83,%eax
    movl $512,%ecx
1:  movl %eax,(%edi)
    movl $0,4(%edi)
    addl $0x200000,%eax
    addl $8,%edi
    loop 1b
    lgdt gdt_pointer
    movl %cr4,%eax
    orl $0x620,%eax // PAE, OSFXSR, OSXMMEXCPT; do not enable OSXSAVE/AVX.
    movl %eax,%cr4
    movl $page_pml4,%eax
    movl %eax,%cr3
    movl $0xc0000080,%ecx
    rdmsr
    orl $0x100,%eax // EFER.LME
    wrmsr
    movl %cr0,%eax
    andl $0xfffffff3,%eax // clear EM and TS
    orl $0x80000003,%eax // PG, PE, MP
    movl %eax,%cr0
    ljmp $0x08,$_start64
.code64
.global _start64
_start64:
    movw $0x10,%ax
    movw %ax,%ds
    movw %ax,%es
    movw %ax,%ss
    leaq __stack_top(%rip),%rsp
    movq %rsp,boot_rsp(%rip)
    xorq %rbp,%rbp
    call smoke_main
2:  hlt
    jmp 2b
.p2align 3
gdt:
    .quad 0
    .quad 0x00af9a000000ffff
    .quad 0x00cf92000000ffff
gdt_end:
gdt_pointer:
    .word gdt_end-gdt-1
    .long gdt
.section .bss.boot_tables,"aw",@nobits
.p2align 12
page_pml4: .skip 4096
page_pdpt: .skip 4096
page_pd:   .skip 4096
.section .note.GNU-stack,"",@progbits
