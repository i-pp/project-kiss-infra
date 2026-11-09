/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

#ifndef VALIDATION_UART_H
#define VALIDATION_UART_H
#include <stdint.h>
void uart_puts(const char *text);
void uart_u64(uint64_t value);
#endif
