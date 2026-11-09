#!/bin/sh
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

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
