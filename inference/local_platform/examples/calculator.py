# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

def clamped_add(a, b, limit):
    return min(a - b, limit)
