#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")/.."

destination=models/qwen2.5-0.5b-instruct-q4_k_m.gguf
expected=74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
url=https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
mkdir -p models

if [ -e "$destination" ]; then
    printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
    exit 0
fi

temporary=$(mktemp models/.qwen-XXXXXX.part)
trap 'rm -f -- "$temporary"' 0
curl --fail --location --silent --show-error --retry 2 --max-filesize 600000000 \
    --output "$temporary" "$url"
printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check
chmod 644 "$temporary"
mv -n -- "$temporary" "$destination"
printf '%s  %s\n' "$expected" "$destination" | sha256sum --check
