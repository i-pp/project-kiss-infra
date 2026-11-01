# Model verification cache

CPU-only optimization implemented; old finite-trial launchers and results are unchanged.

## Attribution

The measured ~180 seconds belong to our evaluation harness, not the vLLM or SGLang loaders. The call chain is `run_vllm_once.execute -> Trial.execute -> verify callback -> paced_assets_v3.verify`. SGLang's later harness uses the same paced verifier. It reads all 20 pinned Next files (48,278,252,061 bytes) at 256 MiB/s, giving a nominal 179.85 seconds. vLLM's successful run recorded verify_assets_start 0.040s and unload30b_intent 179.963s. No model was unloaded until this CPU/file phase finished.

The ordinary localhost llama.cpp router uses `model_runtime.Runtime.prepare -> /models/unload -> /models/load -> readiness GETs`, with registry/file identity checks rather than this full model SHA loop. No removal is needed on that path. SHA of a small registry or Docker configuration fingerprint is unrelated to full model reads.

Strata has separate extracted-engine artifact hashing in `host_trial/assets.verify` and pack/source/semantic verification. Its retained-pack proposal calls that before reserving its attempt; later full_verify includes actual GGUF/pack validation. That is not the same Next 180-second loop. This change does not bypass publisher/license checks, native pack verification, or claim Strata inference works.

Custom download-model.sh/download-coder.sh rehash existing destinations when the download command is rerun; other download scripts validate acquisition/resume. Those are provisioning commands, not router switching. Their checks remain intact.

Hugging Face documents revision-based snapshots/blobs to avoid repeated downloads, including symlink snapshots. These semantics do not supply this application's trusted full-hash evidence. Our fixed Next files are regular local files; we do not change hub/Transformers sources or treat blob names as proof.

Ollama upstream server/images.go places large blob verification in pull handling; ordinary GetModelForRunner parses manifests/model metadata. This reference is current upstream, not attestation of an installed local Ollama version. `ollama` and huggingface_hub were not found in this task's PATH/Python; host/container installations remain unverified. Do not infer every Ollama model switch has this 180s cost. Do not disable its pull integrity checks.

Sources: https://huggingface.co/docs/huggingface_hub/guides/manage-cache and https://github.com/ollama/ollama/blob/main/server/images.go .

## Use

Install the two additive modules alongside fixed_trial_assets.py in next_shared. CPU-only CLI:

```bash
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/next_shared/cached_next_assets.py --cache-dir <OWNER_ONLY_PRIVATE_CACHE>
```

`--force-full` is required after uncertainty, untrusted filesystem/offline changes, or operator-requested verification. First use and changed evidence automatically require a full hash. The CLI uses the existing pinned Next manifest and model path. It cannot load/stop a model or make a generation request.

Future harness integration: instantiate `v = CachedNextVerifier(private_cache, report=logger)` and supply BOTH `Trial(verify=v, unchanged=v.unchanged)`. Current Trial invokes unchanged only at final cleanup. A future launcher must explicitly call `v.assert_unchanged()` before loading and after API readiness under the shared lifecycle lock; these hooks are not wired into old single-use launchers. Existing one-shot approved scripts remain pinned; their attempt counts and permissions are unchanged.

## Trust and change handling

Cache reuse is explicitly local-trust metadata assurance, not cryptographic evidence against root, a malicious owner, a compromised kernel, or metadata-forging remote filesystems. The caller's pinned manifest is the digest/revision authority. Cache provenance is a successful full byte hash produced by this implementation, bound to every manifest row, model/revision, canonical absolute path, directory identity, and all file identities. Legacy receipts without current ctime provenance are not silently imported.

The cache directory/record/lock are owner-only. No symlink ancestor is followed; directories and files are opened through O_NOFOLLOW directory descriptors. All file descriptors remain open across verification; checks include dev/inode/size/mtime_ns/ctime_ns/uid/mode. Every file and model directory is rechecked before publication. Missing, changed, replaced or invalid evidence cannot yield a hit. Extra files are rejected; acquisition.json is the existing allowed non-model receipt. A changed revision/manifest selects new evidence. No asynchronous use before verification occurs.

An exclusive nonblocking cache lock serializes cache writers. Full hashes are published by exclusive temporary file, fsync, atomic rename and directory fsync. Concurrent model mutation during verification fails; a hash mismatch never publishes a new success record. Model files must be regular owner-controlled files without group/other write permission.

The cache lock does NOT stop arbitrary processes writing a model. Backend path reopens after the verification function returns cannot be made atomic by metadata checks alone. Model provisioning must use the same lifecycle lock, finish writes/atomic replacement before verification, and remain excluded through load; loaders retain the verified files thereafter. If that trust/exclusion cannot be established, force a full check and do not load until writers stop. Even a full hash cannot prevent a malicious writer changing a file after verification; stronger integrity requires separately approved immutable/fs-verity/snapshot measures, not a claim made by this cache.

## Measurement and next GPU sequence

`measure_next.py` is a local CPU-only measurement utility. It performs a fresh full SHA verification followed by three unchanged cache hits, reports bytes actually read, monotonic wall time and process CPU time. No model import, GPU initialization, API startup or generation occurs. Local measurement JSON is kept out of the repository; cold hashing retains the existing rate/budget and access-pattern hint, never drop_caches/DONTNEED.

Existing vLLM baseline: overall336.617s, asset phase179.923s, model weights27.56s (server log), engine profile/KV/warmup64.49s (server log), HTTP call7.850s including route checks, ACK9 output tokens. These phases are nested/partly overlapping and must not be summed as disjoint GPU timings. GPU initialization alone is not separately measured. Prior SGLang overall334.968s also includes ~180s assets and first-request JIT; one short ACK is not a sustained decode benchmark.

After MCP restoration and separate coordination, proposed bounded validation is one fixed vLLM/Next warm-cache startup, startup300s/whole900s, API readiness only (zero generation), existing32GiB/swap0 and host swap32GB, exclusive GPU, owned cleanup and30B restore. Log verifier, loader, GPU/profile markers and API-ready separately. Do not consume the old Strata approval or rerun completed vLLM attempts. A new lifecycle measurement record is needed before executing this proposal. No GPU operation has been performed for this optimization.

## CPU measurement result

Actual fixed Next20-file manifest verification read48,278,252,061bytes in179.854632s (processCPU26.488627s). Three unchanged hits read0modelbytes and took0.001037/0.000509/0.000476s. These measure only verification, not GPU/backend startup. Silent storage corruption without metadata changes is not detected on cache hits; force-full is necessary when integrity is uncertain. Cache is an operational optimization, not a replacement for acquisition integrity or immutable storage.

## Maintained integrated entrypoint

The new `warm_cache_startup.py` now invokes the cache on the real inherited evaluation path and explicitly checks identities before unload, immediately before start and after API Ready. It overrides generation to submit zero inference POSTs. See [WARM_CACHE_STARTUP.md](WARM_CACHE_STARTUP.md). Old one-shot scripts remain untouched. This integration has fake-driver/HTTP tests and independent review; no real startup comparison has been run yet.
