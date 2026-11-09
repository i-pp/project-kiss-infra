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
