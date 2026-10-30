# One terminal trial record resolution

Owner approval Sentinel_6c0fb32e13908191bf086409fc0a8cec replaces the brittle fixed-swap admission criterion for this one completed trial's historical record. The resolver does not allocate/load/generate. Current resource telemetry is saved, or explicitly marked unavailable, and is not an admission gate for this bookkeeping operation. Normal runtime/experiment resource guards are unchanged; new work still needs its own authorization and fresh preflight.

## Codex saved-evidence check

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/resolve_terminal_record.py --check-saved-evidence
```

This checks recognized source hashes, the immutable original trial/marker and fixed restoration evidence/current boot. No socket/API/model operation or runtime mutation occurs. Success FIXED_TERMINAL_CASE_SAVED_EVIDENCE_PASS does not claim current live restoration.

## Normal-host finalization only

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/resolve_terminal_record.py --resolve-human-approved
```

Use a normal nonroot host terminal. Existing Codex-route Docker/coordinator AF_UNIX access was deniedEPERM; this does not imply Python is unavailable. No privileged retry or alternate endpoint is used. Do not rerun router recovery, deploy/resume or model trial commands.

The fixed-case resolver holds the strict existing generation lock; validates immutable run/code/operator/marker evidence with0generationPOSTs/intents and no generation request/response files; preserves the consumed attempt; verifies the former temporaryCID and exactname absent twice; and requires daemon idle, the fixed current router/receipt/image/User/network contract, original30B stopped, current30B-only healthy/idle/context32768/one-slot GET confirmation. All these checks are read-only. Model lifecycle POSTs used historically to unload/restore30B are distinct from the trial's0generationPOSTs.

The resource observer deliberately uses raw boundedGET/status methods, not allocation preflight. It records RAM/GPU/swap values or an explicit probe error. It does not fabricate0or infer that sufficient resources exist for future work. Raw restoration observations are assigned before validation so a failure preserves the actual observed values; past missing values remain unrecorded.

A unique owner0700 readiness-reconciliation-audits directory receives owner0600 records. The durable resolution.json preserves original marker bytes/hash, summary/attempt hashes, fixed evidence, current restoration and resource metadata. It records the known outcome: environment readiness failure, no generation request sent, qualityUNASSESSED, owned temporary container absent and30Brestored. Original summaryUNKNOWN and the consumed attempt remain unchanged. The exact original stop marker is atomically renamed to UNCERTAIN.original.json within that audit; its text is preserved. Raw marker bytes are durable before commit, but abrupt-power-loss rename namespace durability is not guaranteed.

Success is RESOLVED_ZERO_POST_READINESS_FAILURE_NO_GENERATION. The cleared global stop permits separately authorized future calls to reach their unchanged admission checks; it grants no new vLLM trial, automatic generation, resource-limit change or model switch. No fallible write/probe is scheduled after the atomic archive.

On failure, the original marker remains unless the archive commit already occurred. Read the private failure.json/current_observation and marker/audit state. Do not restart, remove intent/markers, or blindly repeat. A missing response is not proof archive did not occur.

## Verification

11temporary-fixture CPU tests and independent review passed. Cases cover raw-byte/history/attempt preservation, required no-generation proof, request-file/container/slot/boot/case/source changes, durable-write/rename failures, resource variation or unavailable telemetry without allocation, original resource guard unchanged, exact failing snapshot capture and pending-approval block. They are bookkeeping tests, not model capability or live-host finalization evidence. The actual saved-case check is also run from Codex before handoff.
