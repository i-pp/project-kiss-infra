#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/dev-x86_64.py" "$@"
