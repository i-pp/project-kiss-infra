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
