# Fixed readiness timeout diagnosis — staged only

The observed `LocalError:TimeoutError` does not identify a failed HTTP path. Existing `Coordinator.idle()` checks the daemon control socket, then router `/health`, `/models`, and resident slots. A healthy daemon/Tunnel does not establish router health. A boot plus the proposal's `restart: no` makes a stopped router plausible; it is not proof of the current container state. No Docker/API probe was performed by this preparation.

This staging update preserves the fixed reconciliation binding SHA `1198b95c092a8fab31a34b998c68dfc43dff6fec22256313bc8acb68a729515c`, all archive eligibility predicates, common-lock checks, audit-before-rename commit and UNKNOWN/consumed-attempt preservation. The only change to reconciliation observations is a temporary `Runtime.read` wrapper that annotates failure stage, fixed GET path and exception class/safe code, including reads inside existing idle checks. It restores the original method on every exit; it does not retry or alter transport timeouts. Failure before/between those GETs is labelled ambiguously rather than falsely assigned to the daemon.

After parent review/install into the existing host_trial directory, run once from the normal nonroot HOST_CONTEXT terminal:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/reconcile_vllm_readiness.py --diagnose-human-readonly
```

The original owner0600 bindings stay Git-excluded at `<PROJECT_ROOT>/agents/local_llm/.runtime/reconcile-readiness-bindings-vllm-8949115c.json`. The diagnostic also pins the existing deployment receipt SHA `89c464119551929e7a8a63039dd5c1ca7b2e178db1c5b283d6a0de1c8076e90b` and host-state SHA `7be1b1c22697df5e6bdf7f58734dc3f5baa0aae7fee4e5476040b73046e7abe5`; changed evidence blocks instead of selecting another destination. No caller URL/CID/path selection is provided.

The diagnostic holds the same strict existing generation lock while the original UNKNOWN marker remains in place. It verifies the same immutable run/operator/profile/source/marker evidence. It then independently collects:

- two fixed-ID Docker container inspect reads: router CID from the pinned receipt and original 30B CID from the pinned profile;
- selected ID/name/image, Running/Status/Pid/ExitCode/OOMKilled, restart policy, network ID/endpoint/IP/gateway; no env, command, mount, deployment token or arbitrary stderr;
- actual router name/image/network/IP/endpoint equality against the pinned receipt;
- a separate fixed-scope daemon status/idle read (5-second socket deadline), and separately the existing router/resident GET checks with annotated failures.

Docker reads each have a 10-second timeout; read errors are captured once and no privilege retry occurs. Partial probe failures are retained alongside successful probes. The HTTP helper keeps its existing maximum 2 seconds per read and existing overall idle/confirmation deadlines; this is a finite diagnostic, not a boot/readiness wait loop. Each probe reports wall time. The final immutable evidence/marker identity check must still pass before a result is printed.

`READONLY_DIAGNOSIS_NO_RECOVERY` means observations were collected, not that the router is healthy. Inspect individual `ok`/`receipt_matches` fields. No audit directory is created, no marker is archived/changed, and no model/container lifecycle or generation request is sent. No automatic recovery follows an exited router, receipt mismatch or timeout. Parent must review actual observations before proposing a fixed router recovery. No sudo/newgrp, service/security/receipt update or fallback endpoint is used. Without either explicit CLI flag the command remains inert.

24 CPU fake tests pass, including the unchanged 18 reconciliation tests plus read-only partial diagnostics, stopped/stale receipt projection, changed route rejection, GET-inside-idle timeout annotation/method restoration, ambiguous pre-GET timeout and exact Docker read-only metadata projection/no-retry. Tests are not real host recovery evidence.
