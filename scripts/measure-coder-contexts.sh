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
for context in 8192 16384 32768; do
    if [ -e "logs/coder/context-$context.json" ]; then
        echo "Existing context-$context.json must be preserved before another run." >&2
        exit 1
    fi
done
for context in 8192 16384 32768; do
    CONTEXT_SIZE=$context sh scripts/coder-compose.sh up -d --wait --wait-timeout 180
    sh scripts/coder-compose.sh logs --no-color llama-server > "logs/coder/context-$context-startup.log"
    python3 scripts/coder-benchmark.py "$context"
done
