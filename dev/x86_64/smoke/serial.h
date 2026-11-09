/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

#ifndef VALIDATION_SERIAL_H
#define VALIDATION_SERIAL_H
#include <stdint.h>
void serial_init(void);
void serial_puts(const char *);
void serial_u64(uint64_t);
#endif
