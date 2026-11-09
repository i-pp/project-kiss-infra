#!/bin/sh
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

set -eu
cd -- "$(dirname -- "$0")/.."
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
test "$LOCAL_UID" -ne 0 || { echo 'Non-root execution required' >&2; exit 1; }
kfd_gid=$(stat -c %g /dev/kfd)
render_gid=$(stat -c %g /dev/dri/renderD128)
test "$kfd_gid" = "$render_gid" || { echo 'GPU device GIDs differ: stop' >&2; exit 1; }
export GPU_GID="$kfd_gid"
export VLLM_CONTEXT="${VLLM_CONTEXT:-8192}"
case "$VLLM_CONTEXT" in ''|*[!0-9]*) echo 'VLLM_CONTEXT must be an integer' >&2; exit 1;; esac
test "$VLLM_CONTEXT" -gt 0 && test "$VLLM_CONTEXT" -le 8192 || { echo 'B1 context limit is 8192' >&2; exit 1; }
exec docker compose -f inference/vllm-b1/compose.yaml "$@"
