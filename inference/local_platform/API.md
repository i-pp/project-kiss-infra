# Local inference v1 contract

This documents the implemented, product-independent GPU API at PR1 head
`b433d4727e99fd69f8857a13d970da314b418720`. Existing `aceis-*` deployment names
are compatibility identifiers. Codex, OpenAI and MCP emulation is not required.
The `/v1/chat/completions` compatibility route is not the standard client path and
is not a complete OpenAI API. No native Ollama endpoint is exposed to clients.

## Transport and authorization

- HTTP/1.0 JSON over an absolute owner-only Unix socket; parent0700/socket0600.
- Server verifies peer UID with Linux SO_PEERCRED. This is a same-user boundary,
  not separate-user authorization or a remote bearer-token scheme.
- Host must be `localhost` or `127.0.0.1` without a port. No Origin header or
  Transfer-Encoding. JSON POST has exactly one Content-Length and body<=32768B.
- Results use `Cache-Control: no-store`. There is no prompt/completion request log.
  Engine logs are a separate operational boundary.
- No new TCP listener, credential, public sharing or persistent remote access.
  Authenticated PC-B transport requires separate acceptance. Do not tunnel the
  raw Ollama API as a substitute for the guarded endpoint.

## Routes

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

The independent NPU service owns `/health` and `/v1/classify` on its own private
Unix socket. That classification route is not implemented on this GPU endpoint.
Provider/model/execution_verified are distinct evidence; no silent CPU success
is represented as NPU success. Future unified discovery must preserve this failure
independence and explicitly version any incompatible schema.

## Compatibility discipline and deferred work

Existing v1 request fields/status semantics must not change silently. Additive
response fields are allowed. Breaking changes require a new route version and
contract tests against the lightweight client. The current implementation has no
published remote-auth API, quotas by identity, SSE, durable jobs, embeddings or
general agent tool execution. Two-machine/WSL transport, resource-aware multi-client
soak, container packaging/licensing, and optional third-party client adapters are
follow-up acceptance, not implied features.
