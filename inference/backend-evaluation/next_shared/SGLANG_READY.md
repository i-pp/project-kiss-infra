# Next single SGLang trial after resolved readiness record

The earlier vLLM readiness failure is resolved by a durable supplementary record: no generation request was sent, the owned trial container is absent, and resident30B is restored. Its summary remainsUNKNOWN and its attempt staysconsumed; the original marker text was archived. The shared stop is clear. This does not authorize another vLLM trial.

Use only the existing unused SGLang operator SHA1415a4dd161956390ec6a71fdbd0e11ffff623cf010b3a0de7a6e3b21d3f2545. Its fixed official ROCm/gfx1151 image and Next AWQ assets were acquired and reviewed already; no new image, model or inference approval/attempt is created here.

## One normal-host start

```text
bash <PROJECT_ROOT>/agents/local_llm/.runtime/run-sglang-jit-next-once-20261030.sh
```

No source/sudo/newgrp or extra read-only commands are required. The existing script collects normal readonly preflight before reserving the one attempt and unloading30B. Codex's selected route cannot access the fixed Docker/coordinator sockets, so actual host container execution remains in the normal terminal.

The resource baseline is read fresh in this execution under the common lock. Existing nonzero swap is permitted. For only this exact operator SHA, owner approval Sentinel_3b6193357af08191b3a0abab95aa38e4 allows net hostswap growth up to128MiB from that one baseline. Above128MiB aborts; the baseline is never reset after assethashing/startup/reclaim. Other operators/backends retain their prior zero-growth rule. RAMstart>=24GiB, runtime>16GiB, GPU<=58GiB and nonmissing probes remain mandatory. This is independent of terminal-record resolution; its resource guard was not changed. The trial container keeps32GiB memory with equalmemory-swap (no container swap), CPU8/PID512/privateIPC/shm2GiB/read-only/nonroot/capdropALL/nnp/internal network. General/tmp2GiB staysnoexec; only the already-approved JIT cache512MiB permitsexec. Current source includes exact fixed image/endpoint/ownership checks and recovery of only the owned target.

Model settings remain Next AWQ/bfloat16,1GPU/TP1, context4096,1runningrequest, max-total-tokens4096, chunked-prefill512, memoryfraction0.80, Triton attention/MoE, CUDAgraph disabled, no warmup generation, offlineassets. One temperature0/seed42 ACK request with max64outputtokens is allowed, with generation90seconds and no retry. Success is only environment/API/ACK evidence, not coding capability.

## Bounded readiness correction

The total already-approved900seconds and185-second recovery reservation are unchanged. The unused SGLang trial allocates up to300seconds to model load/JIT/readiness, bounded further by the remaining whole budget; generation remains90seconds. vLLM keeps its existing90-second setting and is not run. The longer SGLang startup allocation is recorded in start events and summary. No resource/security threshold is relaxed.

Readonly GET readiness deadline/abort before send or afterconnect is now a known readiness failure. This prevents the old falseglobalUNKNOWN path when no generationPOST occurred. POST outcomes, owner/endpoint mismatches, unconfirmed cleanup/restoration and other genuineuncertainty remainUNKNOWN/no-retry. Recovery is unchanged: stop/terminalinspect/log/removal/absence of the owned temporary container, then restore30B only after cleanup confirmation. Any UNKNOWN must be inspected before another operation.

The previous API source bytes are preserved under a Git-excluded owner-only sourcearchive with originalSHA, leaving historicalsummary/audit/operator evidence unchanged. The portable JIT testfixture records both prior/current proposedsource hashes.

103CPUtests and independent review pass. New cases cover the exactSGoperator scope, measuredsmall hostswap drift,128MiB boundary/excess, unchangedRAM/GPU floors, stickyfirstfailure including probeexception/invalidbaseline, unchangedotherbackendzero-growth and POSTUNKNOWN/no-retry, and boundedpagingtelemetry. ExistingGETreadiness/cleanup/restoration/security tests still pass. This preparation itself performs no generation/GPU/container operation.

## Scoped paging budget and evidence

This128MiB delta is an engineering finiteexperiment cap, not an OOM guarantee or a container memory increase. Keep container32GiB/no containerswap and all other hardlimits as above. A guardfailure remainssticky even if later readings recover. The firstbad snapshot, baseline, delta, limit and approval are recorded in resource_threshold_exceeded and summary. Probe failures preserve unavailable/errorclass rather than fabricated0.

Host swapI/O (pswpin/pswpout, actualpage size and monotonicelapsed) and memoryPSI are sampled atmost1Hz, with atmost32recent records retained. Missing telemetry is explicitUNAVAILABLE and not an extra admissiongate; coreRAM/GPU/swap availability remainsmandatory. No/proc writes/sysctl/swapfile/service/security changes are made. Resource policy is chosen only after main validates the existing immutableoperatorSHA; no genericresource-override flag is exposed.

The lastSG attempt stopped in readonlyassetverification, without consuming the single model-start attempt. Do not create a newoperator or reset attempts. The existinghostcommand above remains the sole nexttrialstart after preparation checks.
