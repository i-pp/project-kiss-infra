/* Infrastructure smoke test only; no AceIS/Abiss semantics are specified here. */
#include <stddef.h>
#include <stdint.h>
#include "uart.h"
uint64_t sad_ref(const uint8_t *, const uint8_t *, size_t);
uint64_t sad_neon(const uint8_t *, const uint8_t *, size_t);
int64_t dot_ref(const int16_t *, const int16_t *, size_t);
int64_t dot_neon(const int16_t *, const int16_t *, size_t);
volatile uint64_t debug_word = UINT64_C(0x1122334455667788);
volatile uint64_t debug_bss;
volatile uint64_t debug_results;
__attribute__((noinline)) void debug_ready(void) { __asm__ volatile("nop"); }
__attribute__((noinline)) void validation_done(void) { __asm__ volatile("nop"); }
static uint32_t random_u32(uint32_t *state) {
    *state = *state * UINT32_C(1664525) + UINT32_C(1013904223);
    return *state;
}
void smoke_main(void) {
    uint64_t el, sp;
    __asm__ volatile("mrs %0, CurrentEL" : "=r"(el));
    __asm__ volatile("mov %0, sp" : "=r"(sp));
    if (el != 4 || (sp & 15) || debug_bss != 0 ||
        debug_word != UINT64_C(0x1122334455667788)) {
        uart_puts("C_ASM FAIL\n"); return;
    }
    debug_ready();
    uart_puts("C_ASM PASS EL1 BSS DATA SP16\n");
    uint8_t a[320], b[320];
    int16_t x[320], y[320];
    // Fixed known-answer checks supplement the independent scalar comparisons.
    for (unsigned i = 0; i < 320; ++i) { a[i]=0; b[i]=255; x[i]=-32768; y[i]=-32768; }
    if (sad_neon(a,b,16) != 4080 || dot_neon(x,y,4) != INT64_C(4294967296)) {
        uart_puts("NEON FAIL known answer\n"); return;
    }
    uint64_t cases = 0;
    uint32_t state = 42;
    for (unsigned pattern = 0; pattern < 4; ++pattern) {
        for (unsigned i = 0; i < 320; ++i) {
            if (pattern == 0) { a[i]=0; b[i]=255; x[i]=-32768; y[i]=32767; }
            else if (pattern == 1) { a[i]=(i&1)?255:0; b[i]=255-a[i]; x[i]=(i&1)?-32768:32767; y[i]=x[i]; }
            else if (pattern == 2) { a[i]=b[i]=(uint8_t)i; x[i]=y[i]=(int16_t)((int)i-160); }
            else {
                a[i]=(uint8_t)random_u32(&state); b[i]=(uint8_t)random_u32(&state);
                // Defined narrowing: produce values already inside the int16_t range.
                x[i]=(int16_t)((int32_t)(random_u32(&state)&65535)-32768);
                y[i]=(int16_t)((int32_t)(random_u32(&state)&65535)-32768);
            }
        }
        for (unsigned offset = 0; offset < 4; ++offset)
            for (size_t n = 0; n <= 257; ++n) {
                if (sad_neon(a+offset,b+offset,n) != sad_ref(a+offset,b+offset,n) ||
                    dot_neon(x+offset,y+offset,n) != dot_ref(x+offset,y+offset,n)) {
                    uart_puts("NEON FAIL pattern="); uart_u64(pattern);
                    uart_puts(" offset="); uart_u64(offset); uart_puts(" n="); uart_u64(n);
                    uart_puts("\n"); return;
                }
                ++cases;
            }
    }
    debug_results = UINT64_C(0x50415353);
    uart_puts("NEON PASS cases="); uart_u64(cases); uart_puts("\nSMOKE DONE\n");
    validation_done();
}
