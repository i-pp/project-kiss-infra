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
