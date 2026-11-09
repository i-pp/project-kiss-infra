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

#include <arm_neon.h>
#include <stddef.h>
#include <stdint.h>
uint64_t sad_neon(const uint8_t *a, const uint8_t *b, size_t n) {
    uint64_t sum = 0; size_t i = 0;
    for (; n - i >= 16; i += 16)
        sum += vaddlvq_u8(vabdq_u8(vld1q_u8(a+i), vld1q_u8(b+i)));
    for (; i < n; ++i) {
        int d = (int)a[i] - (int)b[i];
        sum += (uint64_t)(d < 0 ? -d : d);
    }
    return sum;
}
int64_t dot_neon(const int16_t *a, const int16_t *b, size_t n) {
    int64_t sum = 0; size_t i = 0;
    for (; n - i >= 4; i += 4)
        sum += vaddlvq_s32(vmull_s16(vld1_s16(a+i), vld1_s16(b+i)));
    for (; i < n; ++i) sum += (int64_t)a[i] * b[i];
    return sum;
}
