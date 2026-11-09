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
export MODEL_FILE=Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
export MODEL_ALIAS=kiss-qwen3-coder-30b
export CONTEXT_SIZE="${CONTEXT_SIZE:-32768}"
case "$CONTEXT_SIZE" in
    8192|16384|32768) ;;
    *) echo 'CONTEXT_SIZE must be 8192, 16384 or 32768.' >&2; exit 1 ;;
esac
exec sh scripts/compose.sh "$@"
