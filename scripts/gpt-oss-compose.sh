#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")/.."
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
test "$LOCAL_UID" -ne 0 || { echo 'Non-root execution required' >&2; exit 1; }
kfd_gid=$(stat -c %g /dev/kfd)
test "$kfd_gid" = "$(stat -c %g /dev/dri/renderD128)" || { echo 'GPU GIDs differ' >&2; exit 1; }
export GPU_GID="$kfd_gid"
export GPT_OSS_CONTEXT="${GPT_OSS_CONTEXT:-8192}"
case "$GPT_OSS_CONTEXT" in 8192|16384|32768) ;; *) echo 'B2 contexts: 8192, 16384, 32768 only' >&2; exit 1;; esac
exec docker compose -f inference/gpt-oss-b2/compose.yaml "$@"
