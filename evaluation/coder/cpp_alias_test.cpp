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
#include <cstdint>
#include <limits>
#include <vector>
#include <iostream>
bool append_slice(std::vector<std::uint8_t>&,std::size_t,std::size_t);
int main() {
    size_t count=0;
    for(size_t n=0;n<=64;++n) {
        std::vector<uint8_t> original(n);
        for(size_t i=0;i<n;++i) original[i]=uint8_t(i*17);
        for(size_t off=0;off<=n+1;++off) for(size_t len=0;len<=n+1;++len) {
            auto v=original, expected=original;
            bool valid=off<=n && len<=n-off;
            if(valid) for(size_t j=0;j<len;++j) expected.push_back(original[off+j]);
            assert(append_slice(v,off,len)==valid); assert(v==expected); ++count;
        }
        for(auto off:{size_t(0),n,std::numeric_limits<size_t>::max()}) {
            auto v=original; assert(!append_slice(v,off,std::numeric_limits<size_t>::max())); assert(v==original);
        }
    }
    std::cout<<"C++ self-alias and bounds: "<<count<<" cases PASS\n";
}
