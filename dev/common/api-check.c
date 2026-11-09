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

#include <stdint.h>
extern uint64_t kiss_add_u64(uint64_t, uint64_t);
int validation_api_check(void) {
    static const uint64_t cases[][3] = {
        {0,0,0}, {1,2,3}, {UINT64_MAX,1,0},
        {UINT64_C(0xffffffff),1,UINT64_C(0x100000000)},
        {UINT64_C(0x8000000000000000),UINT64_C(0x8000000000000000),0}
    };
    for (unsigned i=0; i<sizeof(cases)/sizeof(cases[0]); ++i)
        if (kiss_add_u64(cases[i][0],cases[i][1]) != cases[i][2]) return 0;
    return 1;
}
