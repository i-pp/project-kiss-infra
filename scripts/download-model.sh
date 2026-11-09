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

destination=models/qwen2.5-0.5b-instruct-q4_k_m.gguf
expected=74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
url=https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
mkdir -p models

if [ -e "$destination" ]; then
    printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
    exit 0
fi

temporary=$(mktemp models/.qwen-XXXXXX.part)
trap 'rm -f -- "$temporary"' 0
curl --fail --location --silent --show-error --retry 2 --max-filesize 600000000 \
    --output "$temporary" "$url"
printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check
chmod 644 "$temporary"
mv -n -- "$temporary" "$destination"
printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
