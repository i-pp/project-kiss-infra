#!/bin/sh
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
