#!/bin/sh
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
