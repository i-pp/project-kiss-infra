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

#ifndef KISS_GUARDED_H
#define KISS_GUARDED_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <sys/mman.h>
#include <unistd.h>
typedef struct { void *base; size_t mapped; uint8_t *p; } guarded;
static guarded guard_alloc(size_t bytes) {
    if (!bytes) return (guarded){0};
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    size_t data = ((bytes + page - 1) / page) * page;
    size_t total = data + 2 * page;
    uint8_t *base = mmap(NULL, total, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(base != MAP_FAILED);
    assert(mprotect(base + page, data, PROT_READ | PROT_WRITE) == 0);
    return (guarded){base, total, base + page + data - bytes};
}
static void guard_free(guarded g) { if(g.base) assert(munmap(g.base,g.mapped)==0); }
static uint32_t rng_state = 0x12345678;
static uint32_t next_random(void) {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5; return rng_state;
}
#endif
