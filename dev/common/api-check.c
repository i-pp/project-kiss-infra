/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
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
