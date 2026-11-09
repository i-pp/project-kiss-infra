#!/bin/sh
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

set -eu
exec python3 "$(dirname "$0")/dev-x86_64.py" "$@"
