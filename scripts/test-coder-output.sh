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
work=${1:-logs/coder/eval}
mode=${2:-run-tests.py}
case "$work" in logs/coder/*) ;; *) echo 'Work directory must be under logs/coder/' >&2; exit 1;; esac
case "$mode" in run-tests.py|diagnose.py) ;; *) echo 'Unknown test mode' >&2; exit 1;; esac
test -d "$work"
exec docker run --rm --network none --read-only \
    --user "$(id -u):$(id -g)" --cap-drop ALL \
    --security-opt no-new-privileges --pids-limit 128 --memory 2g --cpus 4 --ulimit core=0 \
    --tmpfs /tmp:rw,nosuid,nodev,size=768m \
    --mount "type=bind,src=$PWD/evaluation/coder,dst=/suite,readonly" \
    --mount "type=bind,src=$PWD/$work,dst=/work" \
    --workdir /work project-kiss-code-eval:20261027 python3 "/suite/$mode"
