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

#include <stdio.h>
#include "probe.h"
int validation_api_check(void);
int main(void) {
    struct validation_cpu c=validation_probe();
    printf("FEATURES {\"sse2\":%u,\"xsave\":%u,\"osxsave\":%u,\"avx\":%u,\"avx2\":%u,\"avx512f\":%u,\"xcr0\":%llu,\"avx2_usable\":%u,\"avx512_usable\":%u}\n",
        c.sse2,c.xsave,c.osxsave,c.avx,c.avx2,c.avx512f,(unsigned long long)c.xcr0,c.avx2_usable,c.avx512_usable);
    if (!validation_api_check()) { puts("LLVM_API_EXEC FAIL"); return 1; }
    puts("LLVM_API_EXEC PASS");
    if (!c.sse2 || validation_simd_cases(128)!=3096) { puts("SSE2 FAIL"); return 1; }
    puts("SSE2 PASS cases=3096");
    if (c.avx2_usable) {
        if (validation_simd_cases(256)!=3096) { puts("AVX2 FAIL"); return 1; }
        puts("AVX2 PASS cases=3096");
    } else puts("AVX2 SKIP CPUID/OSXSAVE/XCR0 gate");
    if (c.avx512_usable) {
        if (validation_simd_cases(512)!=3096) { puts("AVX512F FAIL"); return 1; }
        puts("AVX512F PASS cases=3096");
    } else puts("AVX512F SKIP CPUID/OSXSAVE/XCR0 gate");
    return 0;
}
