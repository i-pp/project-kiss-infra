# Strata Flash-Next preparation — not launched

Scope: offline metadata/plan tests only. Current Codex isolation lacks `/dev/kfd`
and the render node; a host-escalated GPU launch would bypass that boundary and is
not used. Engine/CLI were absent from PATH and the representative user installation
locations checked. No binary/model download, install, GPU load or generation was run.

## Fixed inputs and engine

The release tag [v0.2.7](https://github.com/Niko1221/Strata/releases/tag/v0.2.7)
resolves to commit `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`.
The release now includes a 0.2.7.1 update, but its notes keep Linux x86_64 HIP
engines at0.1.52. [Release assets](https://github.com/Niko1221/Strata/releases/expanded_assets/v0.2.7)
publish SHA-256 for engine0.1.52 halo and Control0.1.53. Fixed release API metadata
confirms169,966,238 bytes for the engine and99,446,914 for optional Control. The JSON
records exact sizes, origins and hashes; neither archive was fetched. The first
trial proposes the engine with pinned source, not automatic Control acquisition.

[Fixed setup.py](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/setup.py)
pins exactly the stored Flash Q2_0 revision, two shard names, sizes and historical
hashes. Current file sizes match; both66.4GB shards were fully rehashed in68.592seconds by the main task on2026-10-29 and matched, with source metadata unchanged. Main weights need
no duplicate download. This is a specific supported input, not arbitrary GGUF support.
Coder-Next Q4_K_M and gpt-oss MXFP4 have no verified Strata path in the checked model
families; they remain unsupported/unknown for this investigation.

The [engine package specification](https://github.com/Niko1221/Strata/blob/v0.2.7/packaging/ENGINE-COMPONENT.md)
and [HIP build recipe](https://github.com/Niko1221/Strata/blob/v0.2.7/packaging/build_hip_linux.sh)
describe a self-contained HIP package: HIP/hipBLAS/hipBLASLt/rocBLAS, comgr/LLVM,
kernel data and matching tuning table with `$ORIGIN` runtime paths. The host amdgpu
kernel and accessible devices are still required. No host ROCm, ttm or IOMMU change
is proposed. The exact extracted library set and signed manifest must be checked
before any approved execution.

## Preparation and resources

The official AVX512 Q2_0 setup branch creates a Strata pack (~40GB extra disk), index
and tokenizer from shard1; shard2 remains the lookup-table input. AVX512f is present
on this host. At the check, disk free was about1.45TB. Packing peak RAM is unmeasured.
The ordinary model reference is ~34GB CPU experts plus ~6GB other model memory;
it is not an EVO-X3 measurement and exceeds the old32GiB evaluation-container cap.
Do not relax caps or adopt `--expert-cache auto` without a reviewed UMA budget.

Preparation commands for a reviewed host execution context, **not executed here**:

```text
python <PINNED_SOURCE>/tools/strata_pack.py build --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/strata_pack.py verify --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/pack_index.py --pack <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/strata_tokenizer.py --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR> --check
```

Use a new output directory; preserve source shards. Do not use `--force` to replace
an existing pack or skip input integrity checks. The upstream builder's verify
step must succeed. A native GGUF pack (`tools/iq_pack.py`) is an alternative but
is not the AVX512 default and has not been tested locally.

MTP is optional in this fixed release. The verified
[draft switch](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/strata_control/draft_layer.py)
supports `mtp:false`; setup `--mtp off` avoids the draft fetch in a fresh data
directory. Text-only `vision` disabled avoids the additional encoder. Do not run
the general installer unattended: it can acquire dependencies/engine/models and
write config. Preparation should use inspected, pinned tools after action-time review.

## Minimal server and one-call plan

The [fixed server source](https://github.com/Niko1221/Strata/blob/v0.2.7/serve/server.py)
establishes this command shape, with config keys `exe,args,cwd,tokenizer,model_name`:

```text
python -m serve.server --engine strata --config <REVIEWED_CONFIG_JSON> --host 127.0.0.1 --port 8082
```

The config's engine args must name `--pack <NEW_PACK_DIR>`, `--native <FLASH_SHARD1>`,
`--ple-gguf <FLASH_SHARD2>`, a checked expert profile and context8192 for a first smoke.
Set `mtp:false`, no vision/MCP/before_load hooks, parallel1, no browser, no token-fit
truncation, no close-retry/reasoning-loop recovery. An explicit expert-cache slot
budget is now proposed as1024 slots (1.318GiB), context8192 and prefill512.
See `../first_trial/` for the inert config and proposed48GiB native RSS soft stop;
actual memory fit and action-time execution approval remain unresolved. Preserve
the installed engine manifest's integrity/signature checks. Disable its optional
leftover-engine cleanup (`STRATA_KEEP_LEFTOVERS=1`) so the owned process tree is the
only termination target.

After an authorized usable GPU context and new-software execution review:
acquire/verify pinned packages, prepare/verify pack, serialize GPU work with the
current router, unload its resident only through the authorized coordinator, start
the single owned Strata process, GET health/models/props, POST one short text request
to `/v1/chat/completions`, then unload/stop Strata and restore router30B health.
API/engine pass and answer-format pass are separate; no new B4.

The current source implements engine `STOP`/`QUIT`, then20s graceful wait,5s terminate
and20s kill wait. Use only the process identity created by the experiment. Do not
send signals to unrelated GPU work. Common runner must fix overall/start/generation
deadlines and resource thresholds before dispatch, and must stop on UNKNOWN without
resending. No launch command or config here has been executed.

## Offline checks

`python3 -B -m unittest -v test_validate_plan` validates the fixed engine/input identity,
the unsupported architecture distinction, and rejection of unpinned sources,
unexpected assets, namespace/escalation fallback and falsely claimed execution.
`validate_plan.py` has no executable launcher, HTTP client or download implementation.

The next single decision, licensing distinction, disk/RAM/time proposal and human
handoff are consolidated in `../first_trial/README.md` and the repository card
`docs/material-cards/2026-10-29-strata-flash-first-trial.md`.
