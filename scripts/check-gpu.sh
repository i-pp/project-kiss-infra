#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")/.."

mkdir -p models logs
# `run` does not publish service ports. Use the exact service user and devices.
sh scripts/compose.sh run --rm --no-deps --entrypoint /bin/sh llama-server -ec '
    id
    test "$(id -u)" -ne 0
    test -r /dev/kfd && test -w /dev/kfd
    test -r /dev/dri/renderD128 && test -w /dev/dri/renderD128
    /opt/rocm/bin/rocminfo
    /app/llama-server --version
    /app/llama-server --list-devices
'
