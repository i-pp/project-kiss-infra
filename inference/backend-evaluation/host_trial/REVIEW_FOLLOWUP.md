# Follow-up review while acquisition/execution approval is pending

No model weights, engine binary, Docker/GPU runtime, service, or model lifecycle operation was performed.

Independent review found one correctness defect: if an original shard's metadata changed while cleanup or resident restoration was UNKNOWN, source-integrity failure replaced the summary status with FAILED. The fix preserves UNKNOWN and records `source_integrity_error` separately. Two CPU fake regressions cover cleanup-unconfirmed and restore-unconfirmed combined with source changes. Installed Strata suite:65 passed; independent staging rerun:65 passed. Next previously installed suite:40 passed, code unchanged in this follow-up.

Resource checks remain: preflight MemAvailable>=24GiB; runtime MemAvailable<=16GiB, global VRAM>58GiB, observed owned-tree RSS>32GiB, any swap growth abort. Soft native monitoring is not a hard memory cap. PID/starttime/pidfd identities scope signals, and immutable CID/image/owner/token/network checks scope the API trial. Resident30B is restored only after positive owned cleanup; unknown lifecycle or failed recovery does not authorize retry.

Fixed publisher signature, complete inventory, selected entrypoint, and strict-True operator notice acknowledgment are rechecked before Strata execution. Signature/inventory/notice failure prevents trial launch. The code records human notice review; it cannot prove the human read the notices. Acquisition approval alone is not an execution record. No unknown marker was cleared.

The original AF_UNIX status connect was denied EPERM before sending a request and was not retried. Human-host authoritative idle status is still required before any future model operation. Existing CPU-only image inspection procedure remains available; no privileged alternative was used.
