# Alternative backend evaluation: prepared, target inference blocked

The existing llama.cpp three-model practical set remains operational. This work
does not modify its source, registry, receipt, model state or services, and does
not touch agent-orchestrator while mailbox work is in progress there.

## Current decision

|Backend|Coder Next Q4_K_M GGUF|Flash-Next GSQ-RCO Q2_0 GGUF|gpt-oss-120B MXFP4 GGUF|
|---|---|---|---|
|vLLM B1 image|Exact GGUF/plugin/HIP mapping unverified|Exact GGUF/plugin/HIP mapping unverified|Exact GGUF/plugin/HIP mapping unverified|
|SGLang0.5.22|GGUF AMD path unsupported|GGUF AMD path unsupported|GGUF AMD path unsupported; native MXFP4 path targets CDNA3/4|
|Strata pinned HIP-halo|No verified architecture path|Official fixed input reusable after pack preparation|No verified architecture path|

All nine target configurations are currently **BLOCKED / NOT_RUN**; model quality
is **UNASSESSED**. These are dependency/execution-path decisions, not model failures.

The current Codex namespace does not expose `/dev/kfd` or `/dev/dri/renderD128`.
Its default Python has no torch/vllm/sglang, and the native backend commands were
not found in the checked locations. This does not mean the host lacks a GPU.
An already authorized backend API could still be called without local GPU nodes;
the fixed candidate APIs are checked separately using GET only.

No Docker/newgrp/sudo, host broker, additional namespace or host-escalated native
GPU execution is used to get around this boundary. No new credentials, host
settings, model/image/package downloads, backend launches or inference requests
were performed. Raw evidence and live machine values are saved separately in
ignored logs, not in these portable preparation files.

## Executable preparation and read-only checks

From `<PROJECT_ROOT>/inference/backend-evaluation`:

```bash
python3 -B backend_matrix.py
python3 -B backend_matrix.py --observe-api
python3 -B -m unittest -v test_backend_matrix
python3 -B -m unittest discover -s sglang_plan -p 'test_*.py'
python3 -B -m unittest discover -s strata_plan -p 'test_*.py'
```

The first command reads native package/device metadata and existing asset sizes.
The optional API check uses fixed loopback ports only: vLLM8081, SGLang30000 and
Strata8082. It sends GET `/health` and `/v1/models`, never POST, load or generation.
It refuses redirects, bounds responses and stops on401/timeout without retries or
credentials. A vLLM200 empty health body is valid; Strata200/loaded:false is not a
loaded-model PASS. The Strata status GETs were checked in its fixed server source
to avoid accidental lazy loading. Any unrelated model ID is only an observation,
not evidence for a target-model inference test.

25 offline tests passed:10 common matrix/API tests,7 SGLang guards and8 Strata
identity/scope guards. The tests use fakes/temporary files and ordinary processes,
not new namespaces, model runtimes or GPU work.

## vLLM: existing small-model proof is kept separate

The pinned B1 image is
`vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905`.
Saved B1 evidence establishes gfx1151 GPU/API/restart operation for Qwen2.5-Coder
1.5B BF16 and records a long-instruction-following FAIL. It does not establish
the three target GGUFs. Current image state was not reinspected through Docker.

[Pinned vLLM source](https://raw.githubusercontent.com/vllm-project/vllm/5df63a7203cdb9328d824a27b682e77c7b9928be/docs/features/quantization/gguf.md)
requires the out-of-tree GGUF plugin. Plugin presence in the fixed image and exact
tensor mapping/HIP kernels remain unverified. The
[plugin guide](https://github.com/vllm-project/vllm-gguf-plugin) explicitly separates
general architecture registration from GGUF compatibility.

`vllm_plan.py` fixes the image and target IDs and emits an inert native launch draft.
Do not run the old B1 test runner: it creates Docker isolation and assumes the
original30B container and localhost8080 are active, which is no longer this setup.
Do not repeat the1.5B test and count it as a target result. No compatible replacement
checkpoint is downloaded; HF tokenizer/config and exact quantization/kernel support
must be resolved before a target launch.

## SGLang: different weights and runtime would be required

[The official compatibility table](https://docs.sglang.io/docs/advanced_features/quantization)
does not support GGUF on AMD. The pinned0.5.22 HIP GGUF implementation and gfx1151
build are documented in `sglang_plan/sglang-readiness.json`.
The dedicated gfx1151 runtime differs from the Instinct image; neither its kernels
nor a compatible non-GGUF checkpoint are present here. BF16 logical-weight estimates
are not download measurements or fit proofs. No large replacement is fetched.
The source-derived launch draft is conditional and never executed by the guard.

## Strata: the closest concrete route is Flash only

Fixed source: releasev0.2.7, commit
`5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`.
The [fixed setup source](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/setup.py)
pins the same Flash revision/shards as the existing models. Both local shards were
fully SHA-256 checked on2026-10-29, totaling66,423,878,624 bytes, in68.592 seconds;
the hashes match and source file metadata did not change. Main weights need no
duplicate download.

The candidate engine archive is
`strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz`, 169,966,238bytes (162.092MiB) according to
the [official release assets](https://github.com/Niko1221/Strata/releases/expanded_assets/v0.2.7).
Its fixed SHA-256 is recorded in `strata_plan/strata-preparation.json`. Archive bytes/digest were verified from fixed release API metadata; extracted
BUILD ID, manifest contents and bundled notices remain unread because no archive
was fetched.
The documented HIP runtime is bundled; host ROCm/ttm/IOMMU changes are not proposed.

AVX512 setup prepares an additional pack of roughly40GB plus metadata/tokenizer;
packing peak RAM is unmeasured. The source's roughly34GB expert RAM plus6GB other
memory is a reference, not an EVO-X3 measurement, and does not fit the prior32GiB
evaluation cap as stated. Do not relax that cap or select an unbounded expert cache.
MTP and vision are disabled in this preparation, avoiding those extra downloads.

`strata_plan/README.md` records the inspected pack/index/tokenizer command shapes,
server API and process-stop sequence. It is not an automatic installer or launcher.
The native engine, source/dependencies and allowed GPU execution context require
action-time review before execution. A general overnight request does not remove
that requirement or authorize device/privilege changes.

## First feasible experiment, after the blockers are resolved

The finite plan is fixed before dispatch: one candidate at a time, startup90s,
one short generation90s/max128 output tokens, stop45s, resident restore120s; whole
candidate345s, no warmup or retry. Initial context8192, temperature0, seed42.
These settings differ from the existing32K comparisons and are not a ranking.

Use the existing shared coordination lock and current verified router identity,
check no active/UNKNOWN work, and ensure only one GPU inference workload. A new
native runtime must not coexist with multiple large model loads. Preflight RAM
must remain at least24GiB, runtime at least16GiB, GPU usage at most58GiB. Fix the
packing/expert/KV budgets first; do not increase host/container limits to force fit.
Startup/API/cleanup and answer-format verdicts are separate from model quality.
No new evaluator or B4 is created. UNKNOWN is reconciled before any further action.

The remaining concrete handoff is an authorized usable GPU runtime deployment,
with pinned software review and a measured memory plan, followed by one targeted
smoke and restoration of the current router30B. No such deployment is performed
by this preparation tool, and no host command is delegated through MCP or a broker.

## One next decision, no extra runtime trial

The sanitized material card `docs/material-cards/2026-10-29-strata-flash-first-trial.md`
consolidates the exact fixed software, licensing distinction, generated pack disk
budget, native memory proposal, human bootstrap and30B restoration. The portable
`first_trial/` config and6 offline tests are ready; no live controller is implied.
The proposal requires individual Strata acquisition/execution review and a usable
human-operated host context. Existing router caps remain unchanged.
