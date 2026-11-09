// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1

.text
.global call_checked
.type call_checked, %function
call_checked:
    stp x19,x20,[sp,#-96]!
    stp x21,x22,[sp,#16]
    stp x23,x24,[sp,#32]
    stp x25,x26,[sp,#48]
    stp x27,x28,[sp,#64]
    stp x29,x30,[sp,#80]
    mov x19,#19
    mov x20,#20
    mov x21,#21
    mov x22,#22
    mov x23,#23
    mov x24,#24
    mov x25,#25
    mov x26,#26
    mov x27,#27
    mov x28,#28
    mov x29,#29
    bl sum_u32
    mov x1,#1
    .macro CHECK reg, value
    cmp \reg, #\value
    cset x2,eq
    and x1,x1,x2
    .endm
    CHECK x19,19
    CHECK x20,20
    CHECK x21,21
    CHECK x22,22
    CHECK x23,23
    CHECK x24,24
    CHECK x25,25
    CHECK x26,26
    CHECK x27,27
    CHECK x28,28
    CHECK x29,29
    ldp x19,x20,[sp]
    ldp x21,x22,[sp,#16]
    ldp x23,x24,[sp,#32]
    ldp x25,x26,[sp,#48]
    ldp x27,x28,[sp,#64]
    ldp x29,x30,[sp,#80]
    add sp,sp,#96
    ret
.size call_checked,.-call_checked
.section .note.GNU-stack,"",%progbits
