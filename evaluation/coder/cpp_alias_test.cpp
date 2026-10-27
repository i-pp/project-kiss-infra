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
