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

#include <stddef.h>
#include <stdint.h>
#include "probe.h"
void validation_add_ref(uint32_t *,const uint32_t *,const uint32_t *,size_t);
void sse2_add(uint32_t *,const uint32_t *,const uint32_t *,size_t);
void avx2_add(uint32_t *,const uint32_t *,const uint32_t *,size_t);
void avx512_add(uint32_t *,const uint32_t *,const uint32_t *,size_t);
unsigned validation_simd_cases(unsigned width) {
    void (*fn)(uint32_t *,const uint32_t *,const uint32_t *,size_t) =
        width==128?sse2_add:width==256?avx2_add:avx512_add;
    uint32_t a[288],b[288],out[288],ref[288];
    unsigned cases=0;
    for (unsigned pattern=0; pattern<3; ++pattern) {
        for (unsigned i=0; i<288; ++i) {
            a[i]=pattern==0?UINT32_MAX:pattern==1?0:(UINT32_C(1664525)*i+UINT32_C(1013904223));
            b[i]=pattern==0?1:pattern==1?UINT32_MAX:(UINT32_C(22695477)*(i+17)+1);
        }
        for (unsigned offset=0; offset<4; ++offset) for (size_t n=0; n<=257; ++n) {
            for (unsigned i=0; i<288; ++i) out[i]=ref[i]=UINT32_C(0xdeadbeef);
            validation_add_ref(ref+offset,a+offset,b+offset,n);
            fn(out+offset,a+offset,b+offset,n);
            for (unsigned i=0; i<288; ++i) if (out[i]!=ref[i]) return 0;
            ++cases;
        }
    }
    return cases; // 3096 cases per ISA, full output and canaries compared.
}
