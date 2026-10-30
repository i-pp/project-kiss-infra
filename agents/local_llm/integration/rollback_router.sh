#!/usr/bin/env bash
# Human host terminal only. Do not source. No parent-shell options are changed.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    printf '%s\n' 'sourceは禁止です。bash /path/to/rollback_router.sh で実行してください。何も実行していません。' >&2
    return 0
fi
if [[ "$#" != 0 ]]; then
    printf '%s\n' 'Usage: bash rollback_router.sh' >&2
    exit 64
fi
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 70
exec /usr/bin/python3 -B "$script_dir/host_router_maintenance.py" rollback
