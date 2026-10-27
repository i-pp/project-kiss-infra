#include <immintrin.h>
#include <stddef.h>
#include <stdint.h>
#if SIMD_BITS == 128
#define FN sse2_add
#define LANES 4
#define V __m128i
#define LOAD(p) _mm_loadu_si128((const __m128i *)(p))
#define ADD(a,b) _mm_add_epi32(a,b)
#define STORE(p,v) _mm_storeu_si128((__m128i *)(p),v)
#elif SIMD_BITS == 256
#define FN avx2_add
#define LANES 8
#define V __m256i
#define LOAD(p) _mm256_loadu_si256((const __m256i *)(p))
#define ADD(a,b) _mm256_add_epi32(a,b)
#define STORE(p,v) _mm256_storeu_si256((__m256i *)(p),v)
#elif SIMD_BITS == 512
#define FN avx512_add
#define LANES 16
#define V __m512i
#define LOAD(p) _mm512_loadu_si512((const void *)(p))
#define ADD(a,b) _mm512_add_epi32(a,b)
#define STORE(p,v) _mm512_storeu_si512((void *)(p),v)
#else
#error Unsupported validation vector width
#endif
void FN(uint32_t *out, const uint32_t *a, const uint32_t *b, size_t n) {
    size_t i=0;
    for (; n-i>=LANES; i+=LANES) {
        V x=LOAD(a+i), y=LOAD(b+i);
        STORE(out+i,ADD(x,y));
    }
    for (; i<n; ++i) out[i]=a[i]+b[i];
}
