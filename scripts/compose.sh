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

# Discover the shared device group; explicit values take precedence.
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"
if [ -z "${GPU_GID:-}" ]; then
    kfd_gid=$(stat -c %g /dev/kfd)
    render_gid=$(stat -c %g /dev/dri/renderD128)
    if [ "$kfd_gid" != "$render_gid" ]; then
        echo 'GPU devices have different GIDs; review group_add for this host.' >&2
        exit 1
    fi
    GPU_GID=$kfd_gid
fi
export GPU_GID

for numeric_id in "$LOCAL_UID" "$LOCAL_GID" "$GPU_GID"; do
    case "$numeric_id" in
        ''|*[!0-9]*)
            echo 'LOCAL_UID, LOCAL_GID and GPU_GID must be numeric IDs.' >&2
            exit 1
            ;;
    esac
done
if [ "$LOCAL_UID" -eq 0 ]; then
    echo 'LOCAL_UID must be nonzero (non-root container required).' >&2
    exit 1
fi

exec docker compose "$@"
