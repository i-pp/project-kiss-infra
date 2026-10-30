# Existing router recovery after an OS reboot

The saved human-host audit proved the single mismatch was Config.User: the existing router retained the UID:GID used during deployment, while the validator regenerated its expectation from the current shell primary GID. All other20contract checks matched. The original UID:GID came from Compose LOCAL_UID:LOCAL_GID and the deployment helper environment; the routerCID, receipt, ownership label, image and other configuration matched the preserved deployed generation. Changing shells must not change an existing object's expected identity.

The fix uses the exact existing User from the immutable diagnostic, bound to this one existing routerCID. It does **not** change process groups, container Config.User, services, credentials, security settings, restart policy or network scope. The default new-deployment environment and current-UID:GID validation remain unchanged. The internal existing-user constructor override requires a canonical nonroot UID matching the current owner and a recorded existing CID. Compose and deploy are forbidden with this override. There is no caller-selected User, CID, model path, URL or arbitrary command flag.

## What Codex can run

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/recover_router_postboot.py --check-saved-evidence
```

This checks only saved immutable evidence/source hashes and the real preset. It has no TTY/host-context requirement because it does not construct the runtime maintenance object, create a maintenance log, connect any socket, issue HTTP, or mutate runtime state. Success is SAVED_EVIDENCE_AND_PRESET_PASS. It explicitly reports live_container_state NOT_CHECKED.

In the selected Codex route at2026-10-30 10:52UTC, Python and the private diagnostic read succeeded, while direct AF_UNIX connect to the fixed Docker socket, user systemd bus and coordinator socket each returned PermissionError errno1. Socket metadata was readable; even the user bus's permissive mode did not permit connection. This establishes current-route socket denial rather than a Python limitation. No privileged/alternative-endpoint retry was used. No service modification or new access broker is introduced.

## Minimal normal-host operation

After the saved-evidence check passes, the already-approved existing-router recovery remains one child-process command in a normal nonroot host terminal:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/recover_router_postboot.py --recover-human-approved
```

The original host guard remains for actual Docker/coordinator maintenance. Do not source this program, use sudo/newgrp, or run the old deploy/resume command. No new model trial is part of recovery.

The command holds the existing strict owner0600 generation lock; validates the exact old zero-POST vLLM UNKNOWN, consumed attempt and immutable evidence; confirms daemon idle, the old trialCID/name absent, original30B stopped, fixed owned router contract, internal network/peers, RAM>=24GiB/GPU<=58GiB/swap0 and unchanged preset. The full contract uses the bound deployed User and all other protections unchanged.

A durable owner-only before record and exclusive one-start intent precede any mutation. It can issue at most one docker start of the existing approved CID, never create/stop/remove/redeploy. The preserved original30B is not started or stopped. An already-running correct router requires no start. The existing router preset loads30B on startup; no HTTP lifecycle or generation POST is issued.

The old route is preserved/retired before verified candidate publication. Existing maintenance logic rechecks CID/image/ownership, internal network, Docker peer endpoint, private subnet/IP, unchanged container contract and existing90-second GET gate. It publishes a refreshed receipt only after exactly30B loaded, other two unloaded, healthy/idle/context32768/one-slot confirmation. The recovery post-intent maintenance budget is180seconds; existing individual timeouts remain.

Recovery then releases the lock while the original UNKNOWN still blocks ordinary callers. The original fixed reconciler acquires the same lock, repeats old immutable evidence and two fixed trial-absence observations plus current30B/resources checks, writes/fsyncs a private audit preserving marker bytes, then atomically renames the marker to UNCERTAIN.original.json. The original vLLM summary remains UNKNOWN and its attempt remains consumed. The rename commit's power-loss namespace durability is not guaranteed; raw marker bytes and planned result are durable before commit.

Success is EXISTING_ROUTER_RESTORED_AND_READINESS_RECONCILED. No extra vLLM attempt is authorized by this success. The unused approved SGLang trial remains a separate step after health confirmation.

## Fixed evidence and failures

Git-excluded router-existing-user-vllm-8949115c.json is owner0600 and hash-pinned. It binds the fixed profile/marker/state/route/CID/run, exact diagnostic-directory started/failure hashes and the preserved pre-fix maintenance/recovery source bytes. The loader requires all21match flags with strict bool types, user alone false, original30B stopped, clean exited router, generation0 and no start intent. Any changed/missing proof fails closed; no arbitrary GID allowlist is added.

Every attempt records a separate owner0700 router-postboot-diagnostics directory before validation. Failure output preserves the original exception code, named stage and audit path. Bounded private failure records contain selected match flags, numeric User identities and exception frames. Env, raw label token, arbitrary User strings and raw inspect are excluded. Diagnostic-collection or audit-write errors never replace the original guard failure.

--diagnose-human-readonly remains available for a justified future live-inspection problem, but another diagnosis is not required for the now-confirmed GID expectation defect. It returns before state save/start intent/start/route changes/archive. Diagnostic audit creation does not consume the one-start budget.

If any stage fails after start intent, do not rerun/delete the intent or markers. There is no automatic rollback, stop, repeated start or original-container fallback. A gate failure can leave the approved router running with a retired/candidate route pending review. A final reconciliation failure can leave30B ready with the old UNKNOWN preserved. Inspect saved state and choose a specific recovery; do not infer a start did not happen from failed terminal output.

## Verification

26 CPU tests (22 recovery/binding/diagnostic tests and4 existing-user tests) pass, including actual guard reproduction of the old current-GID mismatch, corrected existing-user comparison without mutation, source/hash proof rejection, all other security protections, default new-create GID preservation and override create/deploy rejection. Independent review reproduced all26. The existing maintenance25tests and fixed reconciliation24tests also pass. Fixtures/fake Docker are not real host recovery or model-quality evidence. No actual Docker/model/service action has been performed by Codex.
