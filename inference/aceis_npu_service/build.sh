#!/usr/bin/env bash
set -euo pipefail
[[ $# == 2 ]] || { echo 'Usage: build.sh SDK_ROOT OUTPUT (new file)' >&2; exit 2; }
SDK=$(realpath -e "$1"); OUT=$(realpath -m "$2")
[[ ! -e "$OUT" && ! -L "$OUT" ]] || { echo 'Refusing existing output' >&2; exit 2; }
[[ -d $(dirname "$OUT") ]] || { echo 'Output parent must exist' >&2; exit 2; }
TEMP=$(mktemp "$(dirname "$OUT")/.aceis-worker-XXXXXX")
trap 'rm -f "$TEMP"' EXIT
c++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$SDK/cpp-test/include" \
 "$(dirname "$0")/worker.cpp" -L"$SDK/cpp-test/sdk/onnxruntime/lib" -lonnxruntime \
 '-Wl,-rpath,$ORIGIN' -o "$TEMP"
chmod 700 "$TEMP"
ln "$TEMP" "$OUT"
