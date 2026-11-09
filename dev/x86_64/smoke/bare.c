/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

#include "probe.h"
#include "serial.h"
int validation_api_check(void);
volatile uint64_t boot_rsp;
volatile uint64_t debug_bss;
volatile uint64_t debug_word=UINT64_C(0x1122334455667788);
volatile uint64_t debug_results;
__attribute__((noinline)) void debug_ready(void) { __asm__ volatile("nop"); }
__attribute__((noinline)) void validation_done(void) { __asm__ volatile("nop"); }
static void field(const char *name,uint64_t value) {serial_puts(name);serial_u64(value);}
void smoke_main(void) {
    serial_init();
    if ((boot_rsp&15)||debug_bss||debug_word!=UINT64_C(0x1122334455667788)) { serial_puts("BOOT FAIL\n"); return; }
    debug_ready();
    serial_puts("BOOT64 PASS BSS DATA SP16\n");
    struct validation_cpu c=validation_probe();
    serial_puts("FEATURES {");
    field("\"sse2\":",c.sse2);field(",\"xsave\":",c.xsave);field(",\"osxsave\":",c.osxsave);
    field(",\"avx\":",c.avx);field(",\"avx2\":",c.avx2);field(",\"avx512f\":",c.avx512f);
    field(",\"xcr0\":",c.xcr0);field(",\"avx2_usable\":",c.avx2_usable);field(",\"avx512_usable\":",c.avx512_usable);
    serial_puts("}\n");
    if (!validation_api_check()) {serial_puts("LLVM_API_EXEC FAIL\n");return;}
    serial_puts("LLVM_API_EXEC PASS\n");
    if (!c.sse2 || validation_simd_cases(128)!=3096) {serial_puts("SSE2 FAIL\n");return;}
    serial_puts("SSE2 PASS cases=3096\n");
    if (c.avx2_usable) {
        if (validation_simd_cases(256)!=3096) {serial_puts("AVX2 FAIL\n");return;}
        serial_puts("AVX2 PASS cases=3096\n");
    } else serial_puts("AVX2 SKIP CPUID/OSXSAVE/XCR0 gate\n");
    if (c.avx512_usable) {
        if (validation_simd_cases(512)!=3096) {serial_puts("AVX512F FAIL\n");return;}
        serial_puts("AVX512F PASS cases=3096\n");
    } else serial_puts("AVX512F SKIP CPUID/OSXSAVE/XCR0 gate\n");
    debug_results=UINT64_C(0x50415353);
    serial_puts("X86 SMOKE DONE\n");
    validation_done();
}
