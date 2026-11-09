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

#include <cpuid.h>
#include "probe.h"
struct validation_cpu validation_probe(void) {
    struct validation_cpu c={0};
    unsigned a,b,d,e,maximum;
    __cpuid(0,maximum,b,d,e);
    if (maximum<1) return c;
    __cpuid(1,a,b,d,e);
    c.sse2=(e>>26)&1; c.xsave=(d>>26)&1; c.osxsave=(d>>27)&1; c.avx=(d>>28)&1;
    if (c.xsave && c.osxsave) {
        unsigned lo,hi;
        __asm__ volatile("xgetbv" : "=a"(lo),"=d"(hi) : "c"(0));
        c.xcr0=((uint64_t)hi<<32)|lo;
    }
    if (maximum>=7) {
        __cpuid_count(7,0,a,b,d,e);
        c.avx2=(b>>5)&1; c.avx512f=(b>>16)&1;
    }
    c.avx2_usable=c.avx && c.avx2 && c.osxsave && (c.xcr0&6)==6;
    c.avx512_usable=c.avx2_usable && c.avx512f && (c.xcr0&0xe6)==0xe6;
    return c;
}
