#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/dev-aarch64.py" "$@"
