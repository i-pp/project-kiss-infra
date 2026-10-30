# 120B / Coder Next selection — implemented preparation, deployment pending

2026-10-29. Existing resident30B / four-tool connection remains live and unchanged.
No new model request, load, stop, container operation, namespace, registration,
service, credential or permission change has been performed for this preparation.

## Confirmed current state

- Resident container `project-kiss-phase2-llama-server-1`, immutable image
  `sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15`,
  llama.cpp revision `7aca0d2ea8d92b56911233b822db01f9fbb1ae50`.
- Current server uses a fixed `--model`; no existing model lifecycle manager was found.
  It mounts the existing model tree read-only and publishes localhost8080 only.
- Stopped `project-kiss-large-coder-b3-server-1` is configured for Flash, not Next
  or120B. The previous B3 scripts create/start Docker isolation, so they are not run.
- Existing files match saved sizes: Next Q4_K_M 48,410,992,032 bytes / four shards;
  120B MXFP4 63,387,346,208 bytes / one file; Flash Q2_0 66,423,878,624 bytes / two shards.
  This is metadata verification, not a new full-file hash scan.

## Implemented independent preparation

`model_selection.py` and fixed `model_registry.json` provide inventory, explicit
selection and availability. IDs: `qwen-coder-30b`, `gpt-oss-120b`, `qwen-coder-next`.
Flash is a distinct research-only inventory row and is not selectable. Registry data
contains no command, endpoint or environment and cannot select arbitrary paths/URLs.

```sh
python3 -B model_selection.py list
python3 -B model_selection.py status --profile gpt-oss-120b
python3 -B model_selection.py generate --profile qwen-coder-next --task review --prompt 'Explicit source/specification'
```

Currently the last two return BLOCKED/MODEL_MANAGER_NOT_CONFIGURED for nonresident
profiles, with executed=false and quality UNASSESSED. No fallback, HTTP request,
Docker or model-management operation is attempted. Resident selection delegates to
the original bounded/policy-verified client and shares its lock and uncertainty state.

`selection_extension.py` implements two **unregistered** schemas/handlers:
- `aceis_local_model_status(profile)`: read-only availability, no generation or load.
- `aceis_local_model_generate(profile, task, prompt, max_tokens)`: selected advisory
  generation; no autoload, fallback or arbitrary destination. Nonresident is BLOCKED.

14 new native offline tests and19 existing client tests passed. Fixed preset INI
parses with three allowlisted sections and matches saved32K / partial offload settings.
No engine startup/runtime validation is claimed for the proposal.

## Selected deployment direction and unresolved prerequisite

The existing pinned binary has documented router mode and fixed local INI presets.
It can run model child processes within the same model runtime; model routing itself
needs no Docker/bwrap/namespace creation. `router-presets.PROPOSAL.ini` prepares the
existing files/settings only. Intended router limit: `--models-max 1` and
`--no-models-autoload`, with explicit allowlisted preparation and GET probes using
`autoload=false`. No cache-wide or arbitrary model discovery is exposed by MCP.
Before activation, verify the actual engine catalog is limited to the approved
presets; unexpected entries block management. No download endpoints are used.

**There is no approved, already-running router today.** Converting the current
single-model container requires a maintenance deployment and interrupts resident30B.
Codex will not restart/recreate Docker isolation, spawn a host-side launcher, or
ask a broker to do so to bypass the no-additional-isolation restriction. Initial
runtime preparation must be performed through the user's ordinary authorized
maintenance process, or the parent must establish a policy-compliant execution
environment. A mere MCP permission approval does not resolve this prerequisite.
A declarative Compose and human-only runbook are now prepared in HOST_DEPLOYMENT_REVIEW.md. They have not been applied; there is no host-command MCP or lifecycle broker.

The conservative max-one-model design unloads30B while120B or Next is active.
30B calls during that window return unavailable, not another model. Returning to
30B requires one explicit preparation and verified health. The current container,
model files and archived evidence are not altered by this proposal. Planned runtime
resource cap is32GiB RAM / no swap / CPU8 / PID512, matching B3 upper bounds for the
larger models. This aggregate cap also constrains30B and must be validated during
maintenance; it is not assumed equivalent to its present uncapped container.
Retain non-root/read-only models/no privilege addition/no new host listener, plus
preflight RAM>=24GiB, GPU<=58GiB and monitored RAM>=16GiB/GPU<=58GiB. UMA counters
are reported separately, never summed as independent memory.

## Concrete approval scope to return to parent

1. **Runtime maintenance and impact:** establish router mode in the existing model
   execution environment with only the three fixed assets, max one loaded model,
   the existing pinned binary, same localhost8080 exposure and no new credentials.
   Approve the temporary loss of30B availability and validate32GiB aggregate cap;
   confirm the maintenance execution path satisfies the isolation rule. No action
   is authorized solely by this document.
2. **External MCP4->7 (not registered yet):** add the two prepared operations plus
   proposed `aceis_local_model_prepare(profile)`, enum of the same three IDs. Prepare
   may unload the selected model and load another approved model within the router;
   selecting30B restores it. It acquires the common lock, refuses active/UNKNOWN work,
   checks resources and owns only its specific model operation. No URL/path/command,
   Docker access, downloads, key, arbitrary stop or generic execution capability.
   This third lifecycle handler is a specification, **not implemented**.
3. **Fixed timing for new route:** preparation max120s including unload and <=90s
   startup. New selected inference:120B240s, Next180s,30B85s; outer MCP wall caps
   250/190/90s respectively. Original30B tool keeps its existing90s wall limit.
   The larger limits account for full common-policy prefill; saved120B diagnostic
   PP was22.45tok/s and the existing policy-bearing30B smoke had2723input tokens.
   Cross-tokenizer latency is an estimate, not a fresh measurement. No adaptive
   extension/retry: UNKNOWN blocks further calls until reconciliation.

After concrete approval and actual runtime availability, integrate the bounded
lifecycle/selected-generation routes, update the existing app once and verify its
catalog/health. Existing four operations and canonical policy/guard/fixtures/trust
must be preserved;30B client router-awareness needs regression verification.

## Smallest live E2E after prerequisite and approval

Overall max900s, serial, at most one preparation and one generation per profile,
no warmup, retry or repair. Profiles:120B, Next, then30B restoration/regression.
Each generation uses a distinct exact ACK, output max32tokens, temperature0 seed42,
complete verified common policy and no hidden fixtures. Record request/response,
model identity, final content/finish, policy metadata, latency/tokens, RAM/GPU,
call ID, and cleanup. Output always NOT_EXECUTED/untrusted advisory; no B4 or code
execution. Stop at resource breach or UNKNOWN; never automatically repeat.
Verify one loaded model, no leftover helper,30B final health and Tunnel readiness.
A failed/blocked runtime check is not model quality FAIL. These ACKs establish
selection/transport only and do not re-estimate coding accuracy.

## Sources (pinned to the actual image revision)

- [Router mode, routing, limits and lifecycle API](https://github.com/ggml-org/llama.cpp/blob/7aca0d2ea8d92b56911233b822db01f9fbb1ae50/tools/server/README.md#using-multiple-models)
- [Preset format](https://github.com/ggml-org/llama.cpp/blob/7aca0d2ea8d92b56911233b822db01f9fbb1ae50/docs/preset.md)
- Local `inference/large-coder-b3/versions.lock.json`, unchanged Compose and saved
  diagnostic/environment evidence. Documentation support is distinct from runtime
  verification of this particular deployment proposal.


Detailed human-only maintenance, exact files/services/tools, remaining uncertainties,
downtime and CID-preserving rollback: [HOST_DEPLOYMENT_REVIEW.md](HOST_DEPLOYMENT_REVIEW.md).
