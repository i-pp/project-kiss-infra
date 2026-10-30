# Alternative backend measured host trials — prepared, not executed

Scope: project-kiss-infra only. The existing llama.cpp30B/120B/Next set stays intact.
The scripts here **have not acquired or executed Strata or loaded any model**.
The old64GiB OS-start gate/48GiB RSS proposal is superseded by a staged monitored
trial: OS MemTotal61.43GiB and reported VRAM64GiB are distinct accounting views.
No claim of a fully proved peak or extra additive UMA capacity is made.

`APPROVAL_REQUEST.md` is the exact individual software/weight/human-operation handoff.
A general continue-until-finished request does not authorize unrecognized software,
new large weights, privileges or an execution path that bypasses Codex isolation.

## What is implemented

- `acquire_strata_host.py`: only after an explicit human-host approved flag, fetch
  the exact engine and fixed source archives, verify byte/hash/source Python identities,
  extract with Python data filters into fresh directories, and prepare a new private
  venv from six SHA-locked wheels. No installer/setup.py, engine or model is run.
- `record_reviewed_assets.py`: after operator publisher-manifest/signature/notice
  review, record file hashes and entrypoint into an owner-only file. This is a human
  review record, **not an authorization grant; publisher signature checks are independently enforced**.
- `assets.py`: check all846 pinned Strata Python files,23 gguf Python files, extracted
  bundle hashes, fixed model names/sizes and exact dependencies before a trial.
- `host_strata_trial.py` + `owned_process.py`: one common coordinator lock for the
  whole operation; idle/UNKNOWN preflight; reviewed-source import/dependency check
  before any30B unload; unload only router30B; pilot1-layer pack
  (dense still full) and separate48-layer pack, verify/index/tokenizer; correct model
  chat template; raw native engine with `--mmap-experts --ple-io direct`, context8192,
  prefill512, expert-cache1024, explicit validated EOS IDs, MTP/vision off.
  Confirm the mmap startup marker before **one** `GEN128`/temperature0/seed42.
  Preserve raw output IDs/decode and remove only a verified terminal EOS from display.
- CPU/stages and raw engine are monitored for RSS/RAM/swap/GPU/GTT/disk and deadlines.
  STOP/QUIT then identity-checked pidfd TERM/KILL targets only observed owned processes.
  No killpg, namespace, new session, sudo/newgrp, container broker, or arbitrary MCP.
- On known cleanup, restore the fixed router30B via existing bounded HTTP under the
  already-held lock (no recursive Runtime.prepare). Survivor/UNKNOWN/failed restoration
  remains blocked; no retry, marker clearing, unknown service stop or cap relaxation.
- `inspect_vllm_host.py`: a separate human-host CPU-only metadata check of the exact
  existing B1 image, no pull/GPU/model mount/network, before planning runtime changes.
- `inspect_gguf_header.py`: bounded read-only GGUF metadata inspection; no tensors/model
  imports/hashes. Actual architectures: Next=`qwen3next`, Flash=`qwen4exp`,120B=`gpt-oss`.

These are soft observations. They do not prevent every sudden allocation/OOM, detect
all unobserved transient forks, or guarantee automatic restore after controller SIGKILL.
An operator must inspect survivors/UNKNOWN rather than re-run. New/partial packs are
retained only in the unique owner-private run directory; original shards are never
rewritten, copied or deleted. Standard future build hashing is compared to fixed inputs.

## Human commands, only after the concrete approval

Replace the portable placeholders. Run each as a child process; **do not source**
our scripts and do not paste `set -e` into an interactive terminal. Helpers reject
non-TTY/non-host environments rather than changing privileges or security settings.
The prepared wheel lock is for regular Linux x86_64 Python3.14. Other interpreters
need a newly reviewed lock, not a silent dependency fallback.

1. Bootstrap a **new** directory (model/Docker changes0):

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/acquire_strata_host.py --acquire-human-approved --output <NEW_BOOTSTRAP_DIR>
```

   Review the extracted official manifest/signature/BUILD identity/notices and locate
   its entrypoint. The source uses signed engine manifests; do not bypass them or infer
   verification from an unsigned user JSON. The bootstrap does not run the engine and
   does not replace human software/notice review. Package signatures and files are independently verified with existing OpenSSL.
2. With the prepared venv, record that actual human review. Choose an existing approved
   coordinator runtime relative path under the orchestrator `.runtime/`; do not create
   a new coordinator, socket, credential or service:

```text
<NEW_BOOTSTRAP_DIR>/venv/bin/python -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/record_reviewed_assets.py --bootstrap-root <NEW_BOOTSTRAP_DIR> --engine-root <EXTRACTED_ENGINE_ROOT> --entrypoint-relative <MANIFEST_ENTRYPOINT_RELATIVE> --coordinator-runtime-relative <EXISTING_COORDINATOR_RUNTIME_RELATIVE> --approval-reference <TRUSTED_APPROVAL_REFERENCE> --confirm-publisher-manifest-and-notices-reviewed --output <PRIVATE_REVIEW_RECORD_JSON>
```

3. Read-only asset/dependency check (still no engine/model operation):

```text
<NEW_BOOTSTRAP_DIR>/venv/bin/python -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/host_strata_trial.py --assets <PRIVATE_REVIEW_RECORD_JSON> --check-assets
```

4. Finite measured trial, one generation and30B restoration:

```text
<NEW_BOOTSTRAP_DIR>/venv/bin/python -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/host_strata_trial.py --assets <PRIVATE_REVIEW_RECORD_JSON> --run-approved
```

   Equivalent shell wrapper is `bash .../run_strata.sh ...` with the reviewed venv
   on PATH. The wrapper never modifies the parent shell. Without assets/run approval
   flags it prints PREPARED only. The literal full command must be prepared with actual
   approved private paths before handing it to the operator; placeholders are not runnable.

Read each progress line and the private `summary.json` under
`agents/local_llm/.runtime/backend-trials/`. Do not blindly resume a partial run.
`restoration:UNKNOWN` or cleanup survivors requires investigation with the parent;
never clear `.runtime/UNCERTAIN.json` or the private
`backend-trials/strata-UNCERTAIN.json` merely to force another run. Ctrl-C/SIGTERM during
an owned stage uses its cleanup path and attempts30B restore if quiescence is confirmed.
An interrupted lifecycle submission itself remains UNKNOWN and does not trigger another
load/unload. Its transport runs in the caller thread; no delayed POST worker survives.
Resource progress is printed every5seconds while an owned stage is running.

## vLLM first small human-host check

This does not stop30B, import GPU packages or change the old image. It reads the
image identity first, then runs standard-library distribution metadata only:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/inspect_vllm_host.py --inspect-human
```

Docker permission denial is reported without sudo/newgrp/context/socket fallback.
If the CPU container result is uncertain, reconcile its uniquely named owned instance
before retry. Target inference uses the separate Next proposal in `../next_shared/`.

## Offline validation already possible without any GPU/software acquisition

```bash
python3 -B -m unittest discover -s <PROJECT_ROOT>/inference/backend-evaluation/host_trial -p 'test_*.py' -q
bash -n <PROJECT_ROOT>/inference/backend-evaluation/host_trial/run_strata.sh
```

Tests use source-independent fixture tokenizers, fake coordinators and ordinary
stdlib child processes. They do not create namespaces or execute Strata/Docker.
Passing them is preparation evidence, not model/backend runtime success.

## Recovery failure is a read-only inspection step first

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/inspect_trial_recovery.py --run-id <RUN_ID>
```

This reads saved summary/owned cleanup identities and current router metadata only.
No signal, model load, marker removal or retry occurs. Missing native/summary evidence
never proves cleanup. Preserve UNKNOWN; reconcile it with the operator/parent before
preparing a targeted recovery. The initial54 fixture tests are now supplemented by
3 publisher-signature checks and2 recovery-inspection checks plus signed-entrypoint/coordinator-schema/nonroot checks:63 in this unit.
