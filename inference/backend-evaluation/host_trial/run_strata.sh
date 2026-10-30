#!/usr/bin/env bash
# Execute with bash; never source into an interactive shell.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    echo 'Run with bash /path/run_strata.sh; sourcing refused, no action taken.' >&2
    return 0
fi
trial_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
exec python3 -B "$trial_dir/host_strata_trial.py" "$@"
