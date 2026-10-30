# AceIS local coding adviser

ChatGPT and Codex can select three existing local models through the approved HTTP
router. The normal final state is **30B loaded inside the router**; the original
30B container is retained stopped for rollback. The client uses Python's standard
library and returns coding advice without executing generated code.

## Practical set and measured connection

|Profile ID|Existing model / quantization|Context / GPU layers|Role and evidence|
|---|---|---|---|
|`qwen-coder-30b`|Qwen3-Coder-30B-A3B-Instruct / Q4_K_M|32K / 99|Normal drafting and review helper; earlier Codex and ChatGPT calls plus router restoration verified|
|`gpt-oss-120b`|gpt-oss-120b / MXFP4|32K / 20|Selectable helper; historical diagnostic C/AArch64 repairs passed; current ChatGPT response retrieval verified|
|`qwen-coder-next`|Qwen3-Coder-Next / Q4_K_M|32K / 28|Selectable helper; historical diagnostic code PASS and strict-format FAIL; current ChatGPT response retrieval verified|

Flash Next is a separate research-only inventory entry. Its tested repair failures
are distinct from Coder Next, and it is not selected or loaded by this interface.
Different finite tasks do not establish general accuracy or a model ranking.

On 2026-10-29 the human deployed the router using the existing image and internal
network. The parent ChatGPT connector then completed exactly one generation per
profile, without retries, and restored 30B inside the router:

|Profile|Prepare seconds|Generation response seconds|Backend predicted tokens/s|Requested ACK|
|---|---:|---:|---:|---|
|120B|33.121|23.066|22.232|Exact match, stop|
|Coder Next|32.113|25.338|24.954|Exact match, stop|
|30B restored|15.061|2.898|57.476|Exact match, stop|

The request used `task=draft`, `max_tokens=128` and a model-specific ACK prompt.
Total generation response time includes more than decoding; the backend token rate
is a separate reported metric. These are small transport checks, not performance
benchmarks. Audit begin/end-returned records match every call exactly once; the
initial status through final generation spans 165.534 seconds, within 900 seconds.
The exact response content/metrics were supplied by the parent; audit IDs and final
state were checked independently. Local evidence is in
`evidence/chatgpt-three-model-roundtrip.json` and is excluded from Git.

## ChatGPT MCP use

The existing app exposes seven tools: four reads and three writes. These three
model tools accept only fixed profile IDs:

|Tool|Arguments|Effect|
|---|---|---|
|`aceis_local_model_status`|`profile`|GET state; never load or generate|
|`aceis_local_model_prepare`|`profile`|Explicitly unload the current model and load the chosen profile|
|`aceis_local_model_generate`|`profile, task, prompt, max_tokens`|Generate once from the already loaded profile; no autoload or fallback|

For example, call status first. If 120B is wanted, explicitly prepare it, confirm
READY, then submit the review request:

```json
{"profile":"gpt-oss-120b"}
```

```json
{"profile":"gpt-oss-120b","task":"review","prompt":"Review only this explicit specification and source: <SPEC_AND_SOURCE>","max_tokens":256}
```

The first object is used with status or prepare as appropriate; the second belongs
to generate. After the task, explicitly prepare `qwen-coder-30b` to restore normal
use. The existing `aceis_local_llm_generate(task,prompt,max_tokens)` remains a
30B-specific operation with its original schema. It follows the same verified
router route and returns MODEL_NOT_LOADED while another model is loaded.

The other three operations are the original orchestrator status/list/get reads.
This integration does not enable submit/cancel or expose Docker/commands.

## Codex / local terminal use

From `<PROJECT_ROOT>/agents/local_llm`, status is read-only:

```bash
python3 -B local_llm.py status
python3 -B model_selection.py list
python3 -B model_selection.py status --profile qwen-coder-next
```

An explicitly requested task can use the same fixed selection path:

```bash
python3 -B model_selection.py prepare --profile qwen-coder-next
python3 -B model_selection.py generate --profile qwen-coder-next --task review --max-tokens 256 --prompt 'Review only the explicit specification and source: <SPEC_AND_SOURCE>'
python3 -B model_selection.py prepare --profile qwen-coder-30b
```

Omit `--prompt` to supply explicit text on stdin. Tasks are `draft` and `review`.
For an AceIS helper, pass the bounded task/specification/source, collect the answer,
and review the proposed change independently. The helper has no filesystem tools
and cannot execute commands or tests. Do not interpret its output as executable
instructions or run both CLI and MCP copies of the same request.

Codex CLI status was independently checked READY through the internal-IP route
after the parent E2E. That final check did not generate another response.

## Limits and policy

- One loaded model and one backend slot, shared lock, exact 32K context. Loading
  120B or Next temporarily makes the 30B operation unavailable. Other direct
  backend callers must coordinate through the same entry point.
- Temperature 0, seed 42, no prompt cache/streaming; at most 16384 UTF-8 input
  bytes and 1024 output tokens, default 256. Verified common policy bytes count
  toward the conservative context budget.
- Every generation attaches canonical common policy v1.0, SHA-256
  `8fede5f946fd944485e7095ea27cb4923fb97ebf466d1e4b355ad21a50a00286`.
  Missing/invalid policy stops before backend contact. Output is always
  `untrusted_advisory=true`, `verification_status=NOT_EXECUTED`, `code_executed=false`.
- Prepare has a 120-second total bound. MCP generation wall limits are 250 seconds
  for 120B, 190 for Next and 90 for 30B, including bounded cleanup. The old 30B
  operation retains its 90-second MCP limit.
- Before work: available RAM at least 24 GiB, GPU usage at most 58 GiB. Three runtime
  observations below 16 GiB RAM or above 58 GiB GPU abort the operation. Router
  container limits remain 32 GiB RAM/no additional swap, CPU8 and PID512.
- No new package/backend, model download, paid API, credential, external endpoint,
  extra namespace, generic command execution or Docker socket access is provided.

## Routing, uncertainty and recovery

The human deployment script verifies original CID/config and owned router
CID/generation/image/network/endpoint/private IPv4. It publishes an owner-only
receipt only after the GET gate passes and identity is checked again. Runtime
clients accept no caller-supplied IP/URL/port and refuse stale, malformed, partial
or changed metadata. There are no redirects, proxies, alternate-host retries or
automatic fallback. Host values stay in ignored `.runtime/` files.

The internal network and container protections remain in place. Host processes
and peers on that same internal bridge can reach the router. HTTP model/catalog
checks are not cryptographic container identity; a separate administrator's IP or
container reassignment requires human reinspection before reuse.

`.runtime/UNCERTAIN.json` blocks further generation and model switching. On UNKNOWN,
do not resend, try another profile or automatically remove the marker. Inspect the
operation and read-only state. Selected-generation cleanup may unload only its own
model, and never clears UNKNOWN. Durable remote request-key replay protection is
not implemented; keep orchestration explicit and serial.

The human-only rollback script stops only the owned router, preserves its receipt
as evidence, starts the retained original CID and restores localhost routing:

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/rollback_router.sh" || echo 'Rollback stopped; inspect the displayed log.'
```

Run it as a child process, never source it. Codex does not perform Docker maintenance
or create further isolation. See [the deployment/rollback guide](integration/INTERNAL_IP_ROUTE_IMPLEMENTED.md).

## Verification and remaining limits

101 client/selection/runtime/route/maintenance offline tests plus 11 MCP adapter
tests passed, using fakes, ordinary processes and temporary files; shell syntax
also passed. No tests created extra isolation. Final checks found router30B loaded,
120B/Next unloaded, UNKNOWN absent, daemon/Tunnel READY, swap 0, and unchanged
tested-code hashes. Model filenames/sizes match saved identities; large model
SHA-256 hashes were not recomputed in this final check.

The original container was verified and retained stopped by the human deployment
script. This agent could not independently reinspect Docker because its inherited
socket permissions are insufficient; it did not change groups or bypass that denial.

Namespace-dependent B4 execution remains BLOCKED_NESTED_ISOLATION_FORBIDDEN, with
no unisolated fallback. Historical quality results remain separate from the current
connection success. No additional generation, model switch, commit or push was
performed during final verification.
