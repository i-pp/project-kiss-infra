# SGLang AITER retry: terminal result and lower-concurrency proposal

## Confirmed result

Trial `sglang-9fb70fe1913b42ff91468d8160a7a24e` ended after 138.656 seconds. Environment FAIL; quality UNASSESSED; generation POST intents and requests both 0. Owned cleanup and source-metadata preservation succeeded; the existing router restored only 30B. The spent operator/attempt, source receipt and original logs remain intact.

The first failure at 132.878 seconds was real host swap growth: baseline 13,873,152 -> 149,245,952 bytes; net +135,372,800 exceeds the 134,217,728-byte limit. At that sample MemAvailable=49,227,796,480 and GPU-used=50,401,488,896 bytes. Last retained 31.13 seconds of paging telemetry shows swap-out +114,339,840 and swap-in +7,860,224 bytes, max combined I/O approximately38.65MB/s; PSI avg10 reached0.18. This is actual paging, not the earlier112KiB admission noise. It does not establish host OOM or identify which process's pages were swapped.

RAM and GPU values describe UMA-related accounting; do not add them as independent free/used pools. Container memory=memory-swap=32GiB remains a configured cgroup limit, not a measurement of GPU driver's charged memory. memory.current/peak/events and cache occupancy were not recorded. No cgroup OOM diagnosis or512MiB cache-capacity PASS can be reconstructed from these logs.

## Reached stage

The saved120-line tail reaches `Load weight begin`, `Using CompressedTensorsWNA16TritonMoE (ROCm)` and `Multi-thread loading shards:0/10`. Thus launch progressed beyond the prior fatal `module_aiter_core` import; the source-aligned AITER_JIT_DIR fix advanced execution, without proving every AITER path or successful inference.

A separate optional AITER custom_all_reduce build reports missing gfx1151 `fp8-conversion-insts`; AITER catches it and explicitly disables custom allreduce, then weight loading continues. It is a real compatibility limitation but is not the recorded terminal cause. No ENOSPC appears in the retained tail; earlier lines and nativecache high-water size were not retained. Kernel selection is logged; kernel execution or output correctness is not yet proven.

## Proposed next finite trial (subsequently authorized; native run still pending)

Keep the same image, model, quantization, AITER/Triton512MiB directories, security settings,32GiB limit, resource thresholds including128MiB swap growth from a fixed baseline,4096context,64output, startup300s/onePOST90s/whole900s, serializedGPU and ownedcleanup/30Brestore.

Change only the loader option to:

```
--model-loader-extra-config '{"enable_multithread_load":false,"num_threads":1}'
```

The fixed public source defaults to multithread=True with8workers; false selects the sequential safetensors iterator. Both paths can mmap. The change reduces concurrent shard dictionaries/readers; it is not a switch from non-mmap to mmap, and it cannot guarantee host paging stops. Ten shards total44.93GiB, max shard4.66GiB; do not equate mapped/buffered shard sizes with measured resident memory.

Sources:
- https://github.com/sgl-project/sglang/blob/ebfbd3ea35acf6e9facbe74e627d37c3542e5fc1/python/sglang/srt/model_loader/loader.py#L558
- https://github.com/sgl-project/sglang/blob/ebfbd3ea35acf6e9facbe74e627d37c3542e5fc1/python/sglang/srt/model_loader/weight_utils.py#L1060

Only four other SG source files were image-hash matched previously. These loader files are public fixed-source evidence, not yet attested inside the image. Before unloading30B in the next approved normal-host script, capture/hash/parse the fixed image loader and weight_utils as data only using the existing CPU inspection boundary; stop if the documented option/branch is absent. This check can be combined with the single host start rather than requiring repeated manual probes.

For the next approved trial, add bounded read-only cgroup memory.current/peak/max, swap.current/max, memory.events and selected memory.stat to distinguish anon/file/shmem pressure. Derive paths only from the owned CID and verified running PID/starttime; missing data must be explicit, never relax the existing admission gates. A container exec or new namespace/mount is unnecessary. JIT tmpfs occupancy is a separate missing measurement and must not be inferred from cgroup shmem alone.

## Prepared versus live

A staged candidate patch and112CPU tests cover matching create/inspect argv, unchanged security/resource settings, old profiles unchanged, single attempt reservation, one POST and recovery flows. They are not a native inference PASS. This paragraph records the earlier proposal checkpoint. The owner subsequently approved request Sentinel_eebe661ab2088191ae5612d23ecf4d9f. The source-gated profile, diagnostics and new private operator/launcher are now installed; see SEQUENTIAL_LOADER_RUN.md. No new preflight or GPU attempt has started. Previous launchers remain spent and must not be rerun. No threshold increase is proposed. No model, container, service or host-setting operation was performed by Codex during this analysis.
