# Fixed vLLM readiness UNKNOWN reconciliation — preparation only

This is a one-run human-host reconciliation, not a generic uncertain-state bypass or a model retry. It applies only to `vllm-8949115ca95a4eaba673331925dd4542` and its exact approved operator, profile, original marker bytes, saved summary, start/terminal events, identity, route and log hashes. Bindings are SHA-pinned in the script. The code for the original API runner/assets/helper/client/runtime/endpoint handling is also pinned before import/use.

The saved original remains `UNKNOWN / Unknown:HTTP_STAGE_DEADLINE_BEFORE_SEND`, generation0, request intents0, generation_uncertain=false, cleanup=true and30B restored. Source makes the zero-POST interpretation checkable: fixed `generate_once` writes request/post-intent artifacts before submitting; this run has none, and the summary and all evidence hashes are bound. Start-event CID, temporary-route CID, terminal-event CID and log CID must all match the same immutable container. Consumed vLLM attempt stays present and unchanged. Reconciliation does not convert the failed trial into a success or authorize another vLLM attempt.

## Host command after parent review and installation

Install only the portable `reconcile_vllm_readiness.py` into the existing `<PROJECT_ROOT>/inference/backend-evaluation/host_trial/`. The host-specific bindings remain Git-excluded: install the unchanged preparation file `reconcile-readiness-bindings.json` as `<PROJECT_ROOT>/agents/local_llm/.runtime/reconcile-readiness-bindings-vllm-8949115c.json`, owned by the current user with mode0600. The existing `.runtime` must remain owner0700. The script resolves this fixed runtime location after checking its installed repository layout; it accepts no caller-selected bindings path and checks both private-file metadata and the unchanged SHA256 `1198b95c092a8fab31a34b998c68dfc43dff6fec22256313bc8acb68a729515c`. Do not commit the host-specific bindings or place them beside the tracked helper. Use the normal nonroot host terminal after parent installation:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/reconcile_vllm_readiness.py --reconcile-human-approved
```

There is no set-e/source, sudo/newgrp, additional isolation, credential, service, remount, model generation/lifecycle action, container start/stop/kill/remove, or generic caller-selected URL/run/path. Without the explicit flag the CLI only prints PREPARED.

The normal TTY/HOST_CONTEXT guard is mandatory before socket/Docker observations. The reconciliation-only function opens the already-existing `generation.lock` with O_NOFOLLOW and no create, requires owner0600/single-link regular file, takes LOCK_EX|LOCK_NB, and confirms its inode has not been replaced. It does not alter normal `Client.locked` or add an allow-uncertain flag. This is the narrow operator reconciliation path intentionally holding the same lock while the exact original marker still blocks ordinary clients.

Under that lock it performs these observations only:

1. exact original marker/summary/operator/profile/code/run-file hashes, strict zero-POST/known-cleanup/saved-restoration conditions, no request/post/response artifact, and preserved consumed-attempt binding;
2. fixed immutable CID absent and fixed exact name absent via existing canonical local Docker `container ls -a` filters (two read queries, repeated after API observations);
3. existing Coordinator.idle for the same fixed coordinator, then read-only health, model properties32768/one slot, idle slot and existing resource threshold checks; only30B loaded, others unloaded, no swap;
4. all immutable evidence and marker identity rechecked before commit.

Any failed/missing/ambiguous read or busy/unsafe lock leaves the marker blocking. No privilege fallback or automatic retry is attempted.

## Audited atomic archive

After every read passes, a unique owner0700 directory under `.runtime/readiness-reconciliation-audits/` receives owner0600 `audit.json`. The audit contains all fixed bindings, the entire original marker as base64 and its parsed three fields, original marker/summary/operator/profile/evidence hashes, preserved attempt hash, and actual read-only observations. File and audit/parent/runtime directory fsyncs complete **before** archive authorization.

The exact marker is checked once more, then atomic rename to that unique audit directory's `UNCERTAIN.original.json` is the commit point. It is archived, not deleted. No failure-prone write/probe/fsync is done after that commit. Ordinary descriptor release and result printing follow; an output failure after successful commit is not proof the archive failed, so inspect the audit instead of repeating.

The before-rename audit is durable and contains enough raw marker data to preserve it even if power loss affects the later rename namespace. Post-rename namespace durability under power loss is deliberately **not guaranteed**. After a crash or uncertain interruption, inspect the original and archive paths plus durable audit; do not infer success or recreate/delete markers to force a job. A local rename error before commit leaves the original block, and the audit says archive authorized rather than falsely claiming commit completion.

On success the command prints `RECONCILED_READINESS_ONLY_NO_GENERATION`, the audit path and archived marker path. The original summary remains UNKNOWN byte-for-byte. This releases only the reconciled bookkeeping gate; a separately approved SGLang trial is still an independent human-host command and is not started here.

## Offline evidence

Eighteen tests use private temporary fixtures and fakes only. They cover fixed private runtime bindings storage; successful durable-before-archive/raw-byte preservation; busy/unsafe/missing lock; normal-host guard failure; nonzero/uncertain/other UNKNOWN; request artifact; CID disagreement; code/profile/operator/marker hash changes; live container/name; unhealthy/busy/profile/resource changes; concurrent marker change; audit write/fsync/rename failure; no probes after commit; no repeated job; fixed Docker read-only argv; fixed existing Coordinator read operations; and inert CLI defaults.

No real Docker/API/asset verification, marker change, model lifecycle or generation was performed by this preparation.
