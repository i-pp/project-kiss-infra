#!/bin/sh
# KISS Open License Version 1.0 (KOL-v1)
#
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1
#
# Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
# Contributors may add copyright notices for their own original modifications.
# Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
#
# Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
# without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
#
# Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
# KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
#
# This header is a summary, not a separate license or an amendment to KOL-v1.
# All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

set -eu
cd -- "$(dirname -- "$0")/.."
revision=0ca51122012fe4a20dc82988ee58780b008ce4e3
name=Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
size=17988419552
expected=f6050b4da22869aa3fb9d94bb3314e9fc5a027d4741c1f97761c387d6b2b2335
destination=models/$name
mkdir -p models
if [ -e "$destination" ]; then
    test "$(stat -c %s "$destination")" = "$size"
    printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
    exit 0
fi
# Reserve room for the model plus a 5 GiB margin. Download only this file.
available=$(df -B1 --output=avail models | tail -n 1)
test "$available" -gt "$((size + 5368709120))"
temporary=$(mktemp models/.coder-XXXXXX.part)
trap 'rm -f -- "$temporary"' 0
curl --fail --location --silent --show-error --retry 2 \
    --max-filesize "$size" --output "$temporary" \
    "https://huggingface.co/ggml-org/Qwen3-Coder-30B-A3B-Instruct-GGUF/resolve/$revision/$name"
test "$(stat -c %s "$temporary")" = "$size"
printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check
chmod 644 "$temporary"
mv -n -- "$temporary" "$destination"
printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
