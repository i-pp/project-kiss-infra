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

#define _GNU_SOURCE
#include "guarded.h"
#include <stdio.h>
#if defined(TEST_SUM)
typedef struct {uint64_t sum; uint64_t preserved;} checked;
extern checked call_checked(const uint32_t*,size_t);
#elif defined(TEST_SAD)
extern uint64_t sad_u8_neon(const uint8_t*,const uint8_t*,size_t);
#elif defined(TEST_DOT)
extern int64_t dot_i8_neon(const int8_t*,const int8_t*,size_t);
#endif
static void one(size_t n,int mode) {
#if defined(TEST_SUM)
    guarded a=guard_alloc(n*4);uint32_t *p=(uint32_t*)a.p;uint64_t ref=0;
    for(size_t i=0;i<n;++i) {p[i]=mode==0?next_random():(mode==1?UINT32_MAX:UINT32_C(0x80000000));ref+=p[i];}
    checked got=call_checked(p,n);assert(got.sum==ref);assert(got.preserved==1);
    guard_free(a);
#else
    guarded a=guard_alloc(n),b=guard_alloc(n);
#if defined(TEST_SAD)
    uint64_t ref=0;
    for(size_t i=0;i<n;++i) {
        a.p[i]=mode==0?(uint8_t)next_random():(mode==1?0:255);
        b.p[i]=mode==0?(uint8_t)next_random():(mode==1?255:0);
        int diff=(int)a.p[i]-(int)b.p[i];ref+=(uint64_t)(diff<0?-diff:diff);
    }
    assert(sad_u8_neon(a.p,b.p,n)==ref);
#elif defined(TEST_DOT)
    int8_t *pa=(int8_t*)a.p,*pb=(int8_t*)b.p;int64_t ref=0;
    for(size_t i=0;i<n;++i) {
        pa[i]=mode==0?(int8_t)(next_random()%256-128):(mode==1?-128:127);
        pb[i]=mode==0?(int8_t)(next_random()%256-128):-128;
        ref+=(int64_t)pa[i]*(int64_t)pb[i];
    }
    assert(dot_i8_neon(pa,pb,n)==ref);
#endif
    guard_free(a);guard_free(b);
#endif
}
int main(void) {
    size_t cases=0;
    for(size_t n=0;n<=256;++n)for(int m=0;m<3;++m){one(n,m);++cases;}
    size_t lengths[]={511,512,513,4095,4096,4097,65535,65536,65537,999999,1000000};
    for(size_t i=0;i<sizeof lengths/sizeof lengths[0];++i)for(int m=0;m<3;++m){one(lengths[i],m);++cases;}
    printf("AArch64 independent scalar reference + protected tails: %zu cases PASS\n",cases);
}
