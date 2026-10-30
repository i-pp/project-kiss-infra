# Strata preflight failure and one-retry handoff

The first trial's fixed summary SHA256 is `08399de3515876da66243cf8a95e4b8b471b7c2180aa13a498ee6b6da268790a`.
It records FAILED/NOT_RUN/UNASSESSED, generation0/completed0, restorationNOT_NEEDED, source metadata unchanged, and FileNotFoundError for the expected coordinator socket. No pack/model/engine execution happened before this gate. Retain this result as an environment preflight failure; do not count it as model-quality failure.

The coordinator owner separately diagnosed transient user services lost when the user manager restarted, and restored the same daemon/Tunnel/runtime without changing grant/DB/persistence. Recovery is recorded in the owner's recovery/diagnosis artifacts. The socket name derived from the original fixed runtime is correct; no alternate daemon or new runtime is selected. Current Codex metadata sees the socket recreated after the failed attempt. Codex did not reconnect to the previously denied AF_UNIX endpoint.

Codex successfully ran the existing read-only `--check-assets` mode with the approved private venv:846 Strata+23 gguf Python source files, fixed publisher/package/notices and all6 exact dependencies passed; generation0. This is an example of a stage that does not require human-host execution or a new namespace.

## New retry is pending, not authorized by this file

A pending template is in the task area only. After the parent verifies the owner's NEW retry approval, register that reference/time and approved=true in the owner0600 fixed file:

`<PROJECT_ROOT>/agents/local_llm/.runtime/strata-retry01-approval-20261030.json`

Do not reuse the first approval reference as the retry approval. No live retry approval/intent was created by this handoff. Then the normal human-host command is:

```text
<PROJECT_ROOT>/.cache/backend-evaluation/strata-v027-e0152/venv/bin/python -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/retry_strata_host.py --retry-human-approved
```

The helper binds the exact previous NOT_RUN receipt, requires a fresh single-attempt approval, calls the same host guard+same coordinator idle under the common lock, fsyncs an exclusive retry intent, then invokes the existing finite Trial. Trial repeats idle/resource preflight under its own lock before any unload. Busy/missing socket stops before intent and before model work. A prior retry intent blocks resubmission. No service restart/fallback, new credentials, cap relaxation or new namespace is performed. Existing40min/oneGEN/resource thresholds/owned cleanup/30B restore remain.

The old `host_strata_trial.py --run-approved` path now refuses execution when the known first-run record exists; `--check-assets` stays available. The old initial handoff script must not be reused. This is a legitimate-CLI workflow guard, not an OS boundary against the file owner's arbitrary code execution.

CPU verification:full78 tests passed; independent8 retry-protocol tests passed. No GPU/engine invocation was used in this preparation.
