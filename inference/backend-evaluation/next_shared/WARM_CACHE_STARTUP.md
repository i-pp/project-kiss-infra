# Integrated warm-cache startup measurement

Prepared and tested with fake host/HTTP/driver; no real GPU lifecycle run yet.

The maintained entrypoint is `next_shared/warm_cache_startup.py`. Call graph:

`main -> fixed reviewed vLLM operator record -> real human HOST_CONTEXT guard -> WarmCacheTrial.execute (existing common lock, idle, policy, resource checks) -> CachedNextVerifier -> pre-unload identity check -> fixed owned create -> pre-start check -> LoadBoundaryDriver.start (last identity check) -> bounded existing startup/readiness GET -> post-load identity check -> zero-POST completion -> existing owned cleanup -> 30B restore`.

This explicitly wires the load checks into actual hooks. It does not rely on the historical Trial's final-only `unchanged` hook. Final metadata checks remain enabled too. A detected change before unload prevents any lifecycle action. A change after unload prevents model use and invokes owned cleanup/restoration. If the start outcome is unknown or cleanup cannot prove the owned container absent, historical fail-closed handling preserves UNKNOWN and blocks restoration when unsafe.

The default invocation prints the fixed scope and does nothing. Coordinated execution, only after MCP recovery and no other GPU work:

```bash
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/next_shared/warm_cache_startup.py --execute-coordinated-once --cache-dir <OWNER_ONLY_PRIVATE_CACHE>
```

Use the already CPU-primed cache from the reported measurement. If cache evidence is missing/changed, it performs full CPU verification, records that it primed a cold cache and stops BEFORE reservation/unload/create. It will not disguise that as a warm run. Do not retry a reserved attempt; consult its terminal/audit records.

One new fixed measurement marker (`warm-cache-startup-<scope-digest>.json`) is exclusively reserved immediately before 30B unload, under the common lock. This marker does not reuse vLLM's consumed ACK attempts or Strata's pending approval. The measurement is vLLM/Next only, the fixed existing image/model, 4096 context, sequential single slot, startup300s, whole900s including recovery reserve, no generation POST. Container32GiB/swap0 and512MiB executable JIT scope remain unchanged. The new Monitor32 instance uses the existing user-authorized host swap total32,000,000,000bytes cap and preserves RAM/GPU/boot/capacity checks. Historical8GB modules and service configuration are untouched.

`startup-measurement.json` records verifier mode/bytes/wall/processCPU, phase boundaries before unload/start and after API readiness, start-to-ready wall time, and separately parsed server weight-loading/profile/KV/warmup durations when present. GPU initialization alone is explicitly `null/UNAVAILABLE_NOT_SEPARATELY_INSTRUMENTED`. Server phases overlap; they are not summed as disjoint steps. Missing log timing remains null, not zero. Whole bounded server logs and their completeness flags remain available.

The comparison baseline is the successful `vllm-ccdd6b9aa83b4d2b93f8e66b3b293c79`: asset phase179.923s, reported weight loading27.56s, engine/profile/KV/warmup64.49s, whole336.617s. Its one ACK is not reproduced in this zero-generation comparison. Cache-stage savings are already CPU-measured; actual startup/whole-time savings await the coordinated run. A fresh tmpfs JIT and OS page cache can affect startup, so a single comparison is not a statistical speed guarantee.

The real human TTY/HOST_CONTEXT guard remains in force. No fake TTY, sandbox bypass, new daemon, credential, download, security relaxation, automatic trial retry, commit or push is part of this entrypoint.
