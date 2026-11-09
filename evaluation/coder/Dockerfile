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

FROM ubuntu:26.04@sha256:19fcd1bf268f02b60aca3bd30bd8a6d9a11759a430e32921833e65f16d87348a

# Host packages are untouched. Refuse an unexpectedly large package download.
RUN apt-get update \
 && apt-get --print-uris --yes --no-install-recommends install \
      build-essential rustc gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
      binutils-aarch64-linux-gnu qemu-user python3 > /tmp/package-uris \
 && awk '$3 ~ /^[0-9]+$/ {bytes += $3} END {print "Package download bytes:", bytes; if (bytes > 1073741824 || bytes == 0) exit 1}' /tmp/package-uris \
 && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      build-essential rustc gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
      binutils-aarch64-linux-gnu qemu-user python3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
