# Local inference v1 contract

This documents the product-independent GPU/NPU API. It preserves the GPU v1
contract at PR1 head `b433d4727e99fd69f8857a13d970da314b418720` and adds
capability discovery plus independent NPU classification. Existing `aceis-*` deployment names
are compatibility identifiers. Codex, OpenAI and MCP emulation is not required.
The `/v1/chat/completions` compatibility route is not the standard client path and
is not a complete OpenAI API. No native Ollama endpoint is exposed to clients.

## Transport and authorization

- HTTP/1.0 JSON over an absolute owner-only Unix socket; parent0700/socket0600.
- Server verifies peer UID with Linux SO_PEERCRED. This is a same-user boundary,
  not separate-user authorization or a remote bearer-token scheme.
- GPU POST bodies are<=32768B; only `/v1/classify` permits<=100000B.
- Host must be `localhost` or `127.0.0.1` without a port. No Origin header or
  Transfer-Encoding. JSON POST has exactly one Content-Length.
- Results use `Cache-Control: no-store`. There is no prompt/completion request log.
  Engine logs are a separate operational boundary.
- No new TCP listener, credential, public sharing or persistent remote access.
  Authenticated PC-B transport requires separate acceptance. Do not tunnel the
  raw Ollama API as a substitute for the guarded endpoint.

## Routes

`GET /v1/capabilities` returns API version1, the three GPU models and their
single generation lane, and the optional independent NPU classification contract:
model `ryzenai-quicktest-10class`, input shape `[1,3,32,32]`,3072 float32 values,
ten output classes, one concurrent classification and100000B body limit.
`configured` reports a configured endpoint, not readiness. The classifier is for
plumbing verification; `application_accuracy_verified:false` is deliberate. Read
`/health` for current readiness and actual provider/execution scope.


`GET /v1/models` returns HTTP200:

```json
{"models":["coder-next","flash","gpt-oss-120b"],"context_limit":8192,"max_output_tokens":1024,"max_large_models_loaded":1}
```

`POST /v1/jobs` submits exactly once. Required: model, messages. Optional:
max_tokens(default256, integer1..1024), timeout_seconds(default180, integer1..300).
Only the three model IDs above are accepted. Each message has exactly role
(system/user/assistant) and text content. There are1..32 messages and at most24576
UTF-8 text bytes; the stricter conservative admission budget is
`text_bytes + 64 * message_count + max_tokens + 256 <= 8192`. No tools, URL fetching or URL input objects,
images, per-request backend options or caller-selected layer counts.

```json
{"model":"gpt-oss-120b","messages":[{"role":"user","content":"Explain binary search."}],"max_tokens":256,"timeout_seconds":180}
```

HTTP202 is admission, not completion:

```json
{"id":"0123456789abcdef0123456789abcdef","status":"queued"}
```

`GET /v1/jobs/ID` returns HTTP200 for a retained job:

```json
{"id":"0123456789abcdef0123456789abcdef","model":"gpt-oss-120b","status":"completed","result":{"content":"Example text","finish_reason":"stop","prompt_tokens":12,"completion_tokens":4},"error":null}
```

States are queued, running, completed, failed, cancelled. Terminal jobs have a
result or an error as appropriate. Results may include additional backend
metadata; clients should select documented fields, ignore unknown response keys,
and never treat reasoning metadata as tool instructions. Errors are human-readable
and are not stable machine codes. Unknown/evicted IDs return404. Completed jobs
are retained in process memory with a capacity128 and10-minute creation-age
pruning; restart loses them. This is not a durable job or audit store.

`DELETE /v1/jobs/ID` returns202 with `status:cancellation_requested` for a known
job, including a job already terminal. It does not prove physical provider stop.
Poll the job and check service health. The server cancels active owned work and
uses a physical release barrier; no unrelated provider is killed. Terminal
completed jobs remain completed. Unknown ID returns404.

`GET /health` returns200/status ready or503/status not_ready. GPU health,
resource/fault state, queue depth and optional independent NPU health are included.
These operator telemetry fields may grow; the minimal stable readiness field is
status. NPU unavailable does not by itself make GPU readiness fail. Never infer
NPU execution from GPU readiness.

`POST /v1/recover` with `{}` is an operator action after checking a fault. It
returns recovery_requested, not readiness or replay of a failed job. The standard
client intentionally provides no automatic recovery command. A cumulative swap-I/O
latch requires a healthy-host service restart to establish a new baseline.

Invalid payload/header:400. Unknown route/ID:404. Queue/retention full, stopping,
resource fault or service failure:503. Accepted async jobs report later generation
failure through their terminal job status. Client timeouts/disconnects are not
proof of server rejection. There is no idempotency key or automatic POST retry.

## Scheduling and isolation

One GPU execution lane, queue8, sixteen HTTP handlers. All models use the same
queue and deadlines include queueing, loading and generation. Flash is resident;
only one of Next/120B is loaded. Physical RAM/VRAM reclamation is checked before a
new large model. Deadlines and cancellation do not retry user work. Resources,
stop ownership and bounded recovery are enforced on the server, not entrusted to
the client. Multiple pending clients are bounded, not parallel GPU execution.

## Independent NPU classification

`POST /v1/classify` on this same guarded endpoint accepts only:

```json
{"model":"ryzenai-quicktest-10class","input":[3072]}
```

The array above is a shape illustration, not a valid request. Supply exactly3072
finite numbers in float32 range, optionally omitting the fixed model ID. Bool,
NaN/infinity, unknown fields and arbitrary model IDs are rejected. Values are
rounded to float32 before compact upstream serialization. There is no image URL,
upload or implicit preprocessing. Body<=100000B. The current model's labels,
training provenance, application preprocessing and accuracy are not established.
It must not drive real-world classification decisions.

The bridge verifies the configured NPU socket's0700 parent/0600 socket, ownership,
non-symlink path and connected peer UID. One separate nonqueueing classification
slot forwards exactly one request; another caller gets429. Connect<=1s plus a
bounded response budget gives<=12s total; a timer shuts down only that connection.
Responses are<=16KiB and must identify ready RyzenAI/VitisAI, verified NPU target,
`ort_warmup_profile` verification and explicit `mixed_npu_cpu` or `npu_compute`
scope. Ten finite logits, matching argmax and finite nonnegative latency are
validated. Only documented result fields leave the bridge.

A200 result contains status, backend, model, provider, execution_target,
execution_verified, execution_scope, verification_kind, logits, class_index and
latency_ms. `execution_verified` is warmup ORT-provider execution evidence, not
per-request hardware counters or accuracy. Mixed NPU/CPU work is never relabeled
as all-NPU work. An explicitly CPU-mode backend fails this NPU route rather than
silently succeeding as NPU.

Invalid input/header/route body bound returns400; local or upstream busy429;
missing/not-ready backend, invalid identity/output or uncertain timeout503. No
backend error paths/logs are echoed. No retry, autoload, CPU fallback, NPU worker
kill or NPU supervision is performed here. Closing the client connection stops
waiting, not proven NPU execution; the independent worker has its own10s deadline.
An uncertain outcome must not be automatically replayed.

The GPU queue, fault latch and model lifecycle are not used by classification.
An NPU failure does not trip GPU readiness. A GPU provider fault does not by itself
stop a ready NPU, although stopping the whole Router stops admission to both.
Both consume shared system memory; this small forwarding change is not a general
resource-optimized concurrent scheduler. The NPU service keeps its own runtime
limits/recovery and continues to expose its private direct contract independently.

## Compatibility discipline and deferred work

Existing v1 request fields/status semantics must not change silently. Additive
response fields are allowed. Breaking changes require a new route version and
contract tests against the lightweight client. The current implementation has no
published remote-auth API, quotas by identity, SSE, durable jobs, embeddings or
general agent tool execution. Two-machine/WSL transport, resource-aware multi-client
soak, container packaging/licensing, and optional third-party client adapters are
follow-up acceptance, not implied features.
