/* Validation-only PL011 polling, configuration generated from verified DTB. */
#include "uart.h"
#include "uart_config.h"
static void putc_uart(char c) {
    volatile uint32_t *const fr = (volatile uint32_t *)(UART_BASE + 0x18);
    volatile uint32_t *const dr = (volatile uint32_t *)UART_BASE;
    while ((*fr & (1u << 5)) != 0) { }
    *dr = (uint8_t)c;
}
void uart_puts(const char *text) {
    while (*text) putc_uart(*text++);
}
void uart_u64(uint64_t value) {
    char buf[21]; unsigned n = 0;
    do { buf[n++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (n) putc_uart(buf[--n]);
}
