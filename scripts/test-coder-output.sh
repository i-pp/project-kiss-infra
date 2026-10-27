#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")/.."
work=${1:-logs/coder/eval}
mode=${2:-run-tests.py}
case "$work" in logs/coder/*) ;; *) echo 'Work directory must be under logs/coder/' >&2; exit 1;; esac
case "$mode" in run-tests.py|diagnose.py) ;; *) echo 'Unknown test mode' >&2; exit 1;; esac
test -d "$work"
exec docker run --rm --network none --read-only \
    --user "$(id -u):$(id -g)" --cap-drop ALL \
    --security-opt no-new-privileges --pids-limit 128 --memory 2g --cpus 4 --ulimit core=0 \
    --tmpfs /tmp:rw,nosuid,nodev,size=768m \
    --mount "type=bind,src=$PWD/evaluation/coder,dst=/suite,readonly" \
    --mount "type=bind,src=$PWD/$work,dst=/work" \
    --workdir /work project-kiss-code-eval:20261027 python3 "/suite/$mode"
