# Approved fixed postboot reconciliation — no router start

The router and resident30B were already restored. This command continues only the original zero-POST vLLM readiness UNKNOWN reconciliation. It never starts/stops/creates/removes a container, loads/unloads a model, changes host memory or group settings, or generates. Ordinary runtime and experiment guards, including the original reconciler's zero-swap behavior, remain unchanged.

Owner approval request Sentinel_7833ece37ab88191bd475f21930d6713 permits this one fixed case to reconcile with exactly577536bytes of residual swap under the same OS boot, after at least10seconds of unchanged swap quantity and pswpin/pswpout counters. The fixed baseline is not a caller argument or a generic allowance. RAM available>=24GiB and GPU used<=58GiB are checked on every sample. Positive probe types and unchanged boot are mandatory. Samples must be fresh/monotonic, gaps<=5seconds and the entire stability window<=30seconds. Slow or unavailable final checks fail closed with the original marker intact.

## Saved evidence check from Codex

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/reconcile_restored_swap.py --check-saved-evidence
```

This verifies files/source hashes and current boot only. It makes no socket/API call and no runtime mutation. Success FIXED_RESTORED_SWAP_SAVED_EVIDENCE_PASS does not claim current live stability.

## One normal-host command

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/reconcile_restored_swap.py --reconcile-human-approved
```

Use a normal nonroot host terminal. Python works in Codex, but the selected route's Docker/user-systemd/coordinator AF_UNIX connects were independently denied EPERM. The host-only guard for those operations is retained. Do not run the old whole recovery or deploy/resume commands, remove consumed intents, or retry model requests.

Under the existing strict common generation lock, this command validates the old immutable zero-POST vLLM evidence/consumed attempt/marker and hash-pinned postboot restoration case. The owner0600 case binding links the restored current receipt/state, fixedCID/User/profile, exactly one prior start intent, all21matched contract flags, original30B stopped, successful30B-only GET gate, and resource-only failure under this boot. It pins existing recognized source and the stability policy before importing them.

Live checks reuse the existing maintenance ownership/resource/security/path contracts and private internal endpoint verification with verify_only=True. The original30B must remain stopped; the known router must already be running and have no paused/restarting/dead/OOM state. Existing network identity/peer, readonly source/preset and route checks remain. The old vLLM temporaryCID and exactname must be absent before and after current healthy/idle30B/context32768/one-slot checks. The daemon must be idle.

After the10-second resource observation, all live/fixed evidence is checked again, and another fresh sample is taken just before committing. A unique owner0700 readiness-reconciliation-audits directory contains owner0600 audit/precommit files with original marker bytes, unchanged summary/attempt hashes, current health, absence checks and stability evidence. Atomic rename then moves the exact original marker into that audit as UNCERTAIN.original.json; it is not deleted or overwritten. The original trial summary remainsUNKNOWN and attempt remainsconsumed. Raw marker bytes are durable before commit, but rename namespace durability across abrupt power loss is not guaranteed. No fallible probe/write is scheduled after the rename.

Success is RECONCILED_FIXED_RESTORED_SWAP_NO_GENERATION. It does not authorize new vLLM inference or change SGLang trial limits. If output is missing/uncertain, read the audit and marker state before any action. On failure, the private failure.json records stage, current observation, accepted samples and last attempted raw resource value; no automatic retry/start/rollback occurs. The marker remains unless the atomic archive commit already occurred. Do not rerun blindly.

## Verification

21swap-specific CPU tests pass (12continuation/9policy), independently reproduced. They cover exact stable residual, zero/increased/different baseline rejection, boot/RAM/GPU/I/O/probe failures, final live/absence/fixed evidence changes, archive/rename failures preserving original bytes, late resource change capture, untouched original zero-swap behavior and readonly live-check methods. These are temporary-fixture/fake-clock checks; no host container or inference was run. The real saved-case loader is additionally checked from Codex against the actual private restoration evidence before host handoff.
