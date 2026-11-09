/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

#ifndef VALIDATION_CPU_PROBE_H
#define VALIDATION_CPU_PROBE_H
#include <stdint.h>
struct validation_cpu {
    unsigned sse2, xsave, osxsave, avx, avx2, avx512f;
    uint64_t xcr0;
    unsigned avx2_usable, avx512_usable;
};
struct validation_cpu validation_probe(void);
unsigned validation_simd_cases(unsigned width);
#endif
