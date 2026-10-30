#!/usr/bin/env bash
# Run with bash; do not source. No set -e in the parent terminal.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  printf '%s\n' 'Run this script with bash; do not source it.' >&2
  return 2
fi
trial_helpers="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 1
trial_project="$(cd -- "$trial_helpers/../../.." && pwd -P)" || exit 1
trial_python="$trial_project/.cache/backend-evaluation/strata-v027-e0152/venv/bin/python"
if [[ "$#" -gt 1 ]] || [[ "${1:-status}" != start && "${1:-status}" != status ]]; then
  printf '%s\n' 'Usage: bash run_strata_retry02_tmux.sh [start|status]' >&2
  exit 2
fi
exec "$trial_python" -B "$trial_helpers/launch_strata_retry02.py" "${1:-status}"
