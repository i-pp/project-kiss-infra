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

#include <cassert>
#include <charconv>
#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <system_error>
extern "C" int parse_u32(const char*, uint32_t*);
static void test(const std::string& s) {
    uint32_t ref=0, out=0xaabbccdd;
    auto r=std::from_chars(s.data(),s.data()+s.size(),ref,10);
    bool ok=!s.empty() && r.ec==std::errc{} && r.ptr==s.data()+s.size();
    int got=parse_u32(s.c_str(),&out);
    assert(got==(ok?1:0)); assert(out==(ok?ref:0xaabbccdd));
}
int main() {
    uint32_t out=123; assert(!parse_u32(nullptr,&out)&&out==123);
    assert(!parse_u32("1",nullptr));
    for(auto s:{"","0","0000","4294967295","4294967296","+1","-1"," 1","1 ","12x","9999999999999999999999999999999999"}) test(s);
    test(std::string(4096,'0')+"4294967295");
    std::mt19937 rng(42);
    for(int i=0;i<20000;++i) {
        test(std::to_string(rng()));
        test(std::to_string(uint64_t(rng())<<16));
        std::string s; for(unsigned j=0,n=rng()%30;j<n;++j) s+=char(1+rng()%127);
        test(s);
    }
    std::cout<<"C parser: boundary cases + 60000 independent from_chars comparisons PASS\n";
}
