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

#include <immintrin.h>
#include <stddef.h>
#include <stdint.h>
#if SIMD_BITS == 128
#define FN sse2_add
#define LANES 4
#define V __m128i
#define LOAD(p) _mm_loadu_si128((const __m128i *)(p))
#define ADD(a,b) _mm_add_epi32(a,b)
#define STORE(p,v) _mm_storeu_si128((__m128i *)(p),v)
#elif SIMD_BITS == 256
#define FN avx2_add
#define LANES 8
#define V __m256i
#define LOAD(p) _mm256_loadu_si256((const __m256i *)(p))
#define ADD(a,b) _mm256_add_epi32(a,b)
#define STORE(p,v) _mm256_storeu_si256((__m256i *)(p),v)
#elif SIMD_BITS == 512
#define FN avx512_add
#define LANES 16
#define V __m512i
#define LOAD(p) _mm512_loadu_si512((const void *)(p))
#define ADD(a,b) _mm512_add_epi32(a,b)
#define STORE(p,v) _mm512_storeu_si512((void *)(p),v)
#else
#error Unsupported validation vector width
#endif
void FN(uint32_t *out, const uint32_t *a, const uint32_t *b, size_t n) {
    size_t i=0;
    for (; n-i>=LANES; i+=LANES) {
        V x=LOAD(a+i), y=LOAD(b+i);
        STORE(out+i,ADD(x,y));
    }
    for (; i<n; ++i) out[i]=a[i]+b[i];
}
