#!/bin/sh
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

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
