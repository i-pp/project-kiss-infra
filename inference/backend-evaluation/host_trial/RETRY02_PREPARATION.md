# Strata retry02 detached host handoff — pending new approval

This code is prepared for installation beside `host_strata_trial.py` and
`retry02_strata_host.py` in `<PROJECT_ROOT>/inference/backend-evaluation/host_trial/`.
No tmux session, GPU job, model lifecycle operation, or service has been started.
The owner-only retry02 approval record must be registered after the owner approves
the new attempt and cumulative disk limit. The previous retry01 intent remains.

After approval, normal human host terminal command:

```bash
bash <PROJECT_ROOT>/inference/backend-evaluation/host_trial/run_strata_retry02_tmux.sh start
```

This returns after starting the fixed finite job in a dedicated detached tmux
session. Ctrl+C in the original terminal cannot interrupt the detached job.
Do not attach and send Ctrl+C, log out, reboot, or start another GPU workload
while the trial is running. No tmux installation, system service, login startup,
linger, new credentials, or broader host privilege is added. Logout survival is
not promised. The normal host/interactive TTY guard remains mandatory.

Status and result (same command is read-only when `status` is selected):

```bash
bash <PROJECT_ROOT>/inference/backend-evaluation/host_trial/run_strata_retry02_tmux.sh status
tail -n 15 <PROJECT_ROOT>/agents/local_llm/.runtime/strata-retry02-terminal.log
```

The launcher uses an exclusive one-use launch intent, and the trial has its own
exclusive attempt intent and shared generation lock. A missing result or failed
tmux response means pending/unknown; inspect the existing records instead of
launching again. `controller_exit_code` is a process result, not proof of model
quality or successful restoration. The result also includes the controller's
reported summary; verify the saved run summary and external model status.

The wrapper keeps the same child handle/PTY alive through interruption while
the controller performs its finite cleanup and 30B restoration. It does not
kill the controller on an outer timeout, restart it, or issue model requests.
This is best effort process handling; SIGKILL, kernel hangs, or machine shutdown
cannot guarantee automatic restoration. An uncertain owned process or lifecycle
result must block automatic retry and 30B reload.

The previous pilot files have fresh stable-metadata SHA256 evidence. A new run
must match every inventory/hash and manifest identity before reusing that pilot,
then run the fixed read-only pilot verifier before unloading 30B. The interrupted
full pack is unusable and must be preserved; the new full pack uses a fresh path.
Reusing the pilot means no second copy of its approximately 6.54GiB payload.

Capacity proposal: retain the old 40.33GiB run plus 1.24GiB fixed software,
build an estimated 37.53GiB full pack, and reserve 12GiB additional working space:
approximately 91.10GiB cumulative. Request a 120GiB cumulative sampled stop limit,
retain the existing 70GiB per-new-run limit, require 100GiB filesystem free before
starting and stop below 32GiB free during work. These are sampled soft controls,
not filesystem quotas. Current measured free space is approximately 1216.73GiB.
The increase from the previous 80GiB limit requires new approval.

No automatic deletion is performed. After a successful new trial and review,
the old incomplete `full/` directory is a deletion candidate (about 33.78GiB).
Its removal needs a separate explicit instruction; preserve its summary and
verification/provenance records. The old pilot remains an input until all work
using it is complete. This proposal permits exactly one new run, not repeated
accumulation of partial packs.

CPU tests use fake coordinator/child/tmux responses. They validate refusal and
recording behavior; they do not establish real tmux, engine, GPU, or model success.
