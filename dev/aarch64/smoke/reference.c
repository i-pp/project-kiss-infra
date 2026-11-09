/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

/* Independent scalar oracle. This translation unit disables vectorization. */
#include <stddef.h>
#include <stdint.h>
uint64_t sad_ref(const uint8_t *a, const uint8_t *b, size_t n) {
    uint64_t sum = 0;
    for (size_t i = 0; i < n; ++i) {
        int d = (int)a[i] - (int)b[i];
        sum += (uint64_t)(d < 0 ? -d : d);
    }
    return sum;
}
int64_t dot_ref(const int16_t *a, const int16_t *b, size_t n) {
    int64_t sum = 0;
    for (size_t i = 0; i < n; ++i) sum += (int64_t)a[i] * b[i];
    return sum;
}
