#include <cpuid.h>
#include "probe.h"
struct validation_cpu validation_probe(void) {
    struct validation_cpu c={0};
    unsigned a,b,d,e,maximum;
    __cpuid(0,maximum,b,d,e);
    if (maximum<1) return c;
    __cpuid(1,a,b,d,e);
    c.sse2=(e>>26)&1; c.xsave=(d>>26)&1; c.osxsave=(d>>27)&1; c.avx=(d>>28)&1;
    if (c.xsave && c.osxsave) {
        unsigned lo,hi;
        __asm__ volatile("xgetbv" : "=a"(lo),"=d"(hi) : "c"(0));
        c.xcr0=((uint64_t)hi<<32)|lo;
    }
    if (maximum>=7) {
        __cpuid_count(7,0,a,b,d,e);
        c.avx2=(b>>5)&1; c.avx512f=(b>>16)&1;
    }
    c.avx2_usable=c.avx && c.avx2 && c.osxsave && (c.xcr0&6)==6;
    c.avx512_usable=c.avx2_usable && c.avx512f && (c.xcr0&0xe6)==0xe6;
    return c;
}
