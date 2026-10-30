# Existing vLLM image: finite source handoff

The human-host CPU package receipt (user message `Sentinel_e88f0ae0c904819182bf5174db5aa10f`, parent received2026-10-30 05:52UTC) reports:

- image `vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905`
- Python3.12.15; vLLM0.32.0+rocm723; torch2.13.0+git733fca1; Triton3.8.0+git669b31ac
- transformers5.19.0; compressed-tensors0.17.0; safetensors0.8.0
- GGUF plugin/gguf/SGLang absent; generation requests0.

These values satisfy the existing finite Next profile's specified version ranges. GGUF plugin is unnecessary for the acquired safetensors compressed-tensors checkpoint. No install or image modification is indicated by this receipt. The exact SGLang source/runtime is independent.

The source candidate is `5df63a7203cdb9328d824a27b682e77c7b9928be`. A version string does not establish this commit or gfx1151 kernel functionality. `source_probe_manifest.json` pins byte lengths and SHA256 of seven primary-source files: CT loader, MoE dispatch/WNA16, WNA16 oracle, Triton experts, Qwen GDN, CLI arguments. The manifest's SHA is checked in the script. Only391,835bytes of public source text was fetched to compute these baselines. No binary/model was acquired.

## Next human-host CPU-only command

Install this small directory as `<PROJECT_ROOT>/inference/backend-evaluation/vllm_source_handoff/`, beside the existing `host_trial/`. Root owns repository integration. Then use a normal nonroot host terminal:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/vllm_source_handoff/inspect_vllm_source_host.py --inspect-human
```

No `source`, `set -e`, sudo/newgrp, Docker context/socket change, pull, GPU device, model mount, or network is used. The script calls the existing HOST_CONTEXT/TTY guard, reads the fixed image identity, and creates one brief CPU-only metadata container with256MiB RAM/swap total,1CPU,64PIDs,read-only root and16MiB `/tmp`, no-new-privileges/cap-drop ALL. Standard-library metadata/hash operations do not import vLLM/torch/Triton or execute source files. Image/user credential URLs are not printed.

The output contains immutable image ID/digest, selected40hex revision labels, sanitized public-vLLM `direct_url.json` commit metadata, installed package versions, bounded native-extension filename inventory, seven source hashes/matches, and generation0. The source result may be:

- all seven equal, exact commit also reported: strongest available CPU evidence, still not whole-source or GPU proof;
- all seven equal, commit absent/different: equivalence of selected critical paths only; preserve the provenance limitation in the trial record;
- any differing/missing file: review the specific installed critical source before enabling the profile; do not set source-match acknowledgment from version alone.

A missing editable-install path can also produce a missing-file result. Resolve its known source location by read-only metadata rather than importing the package or silently skipping the file.

Permission failures stop; there is no privileged retry. A timeout/interrupt or nonzero CPU command retains the unique owned-container name for read-only reconciliation, no automatic repeat. The image stays unmodified and30B is not unloaded. This human CPU check is separate from GPU-trial authorization.

## Finite GPU profile after source review and parent authorization

Reuse acquired `cyankiwi/Qwen3-Coder-Next-AWQ-4bit@c92cabfad08cadb011dc169cabb3e6da621b0719` and the existing `next_shared/host_api_trial.py`; no duplicate weights, backend installs or new launcher.

- safetensors/lazy; BF16; TP1; `--moe-backend triton`; `--attention-backend TRITON_ATTN`; `--gdn-prefill-backend triton`; `--enforce-eager`
- context4096, max-seqs1, batched-tokens512, GPU-memory-utilization0.80
- AITER off; GDN decode Triton; plugins empty; offline model access; usage telemetry off
- exactly1API POST, output64, temperature0/seed42, retry0; startup90s/generation90s/whole900s; cleanup45s/restoration120s reserved
- only one loaded model; temporarily unload router30B, then restore it only after owned temporary container cleanup is positively confirmed
- start MemAvailable>=24GiB; runtime abort at<=16GiB, globalVRAM>58GiB or swap growth; container32GiB memory/swap total,8CPU,512PIDs,private IPC/read-only/nonroot/no extra capabilities, fixed existing internal-network ownedIP and no host port publish.

The lazy loader may avoid full CPU expansion, but native kernel/JIT, transient repack and32GiB memory feasibility remain real-test questions. A source match cannot prove them. Startup may perform internal dummy/profiling forward work; distinguish this from the single submitted API request. Do not relax caps, timeouts, IPC/security or retry failed generations to force a pass.

Parent must bind the human source receipt, immutable image ID and existing user approval scope to the operator record. This child did not enable runtime flags or issue a GPU command. Source-equivalence limitations belong in a sidecar evidence record if the current operator schema cannot express them. Do not falsely describe seven-file equivalence as a complete installed commit attestation.
