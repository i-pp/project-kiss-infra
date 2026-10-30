#!/usr/bin/env bash
# Human host terminal only. Do not source. No parent-shell options are changed.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    printf '%s\n' 'sourceは禁止です。bash /path/to/deploy_router.sh で実行してください。何も実行していません。' >&2
    return 0
fi
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 70
mode=deploy
if [[ "$#" == 2 && "$1" == --resume && "$2" == --internal-ip ]]; then
    mode=resume-internal
elif [[ "$#" == 1 && "$1" == --internal-ip ]]; then
    mode=deploy-internal
elif [[ "$#" == 1 && "$1" == --resume ]]; then
    mode=resume
elif [[ "$#" != 0 ]]; then
    printf '%s\n' 'Usage: bash deploy_router.sh [--resume] [--internal-ip]' >&2
    exit 64
fi
exec /usr/bin/python3 -B "$script_dir/host_router_maintenance.py" "$mode"
