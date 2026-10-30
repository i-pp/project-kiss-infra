# One SGLang continuation: host total swap8GB

The owner instruction「swapは8GBまでつかっていい」(Sentinel_42154944411881919615f516183bbf1f) is recorded privately and interpreted conservatively as **host total swap used <=8,000,000,000decimal bytes**, not8GiB and notgrowth above baseline. Effective limit=min(user8GB,actualSwapTotal). No capacity, swapfile, sysctl, OS, service, security, credential or grant change is made.

**Ready only: the parent will sequence this command after the separate32MiB/s NPU-record hash finishes. Do not overlap the GPU test or kill that worker.** Use the new private `resume-sglang-total-swap-8gb-once-20261030.sh` via bash in a normal host terminal, never source it. Old start commands remain spent and should not be rerun.

## Same single allowance and evidence

The immutable original operator9f3d6953c389d9bca94020de8b8cdbcaedd4580d458cd78dda57af8073338d96 and its unconsumed GPU marker are retained. New total-swap authorization and one exclusive continuation intent bind both previous zero-lifecycle failures, prior source/asset intents and the successful fixed-image static receipt. All prior evidence remains byte-identical. The actual fixed image ID is read afresh. No new GPU allowance is issued for this or other backends. A fresh total-resource admission check occurs before atomically consuming the original attempt marker, immediately before30B unload.

## Asset and time bounds

Full20SHA, fixed manifest, read-only file access and before/after file identity checks remain. No partial-hash or metadata-only shortcut is used. Read buffer1MiB, aggregate256MiB/s, assets240s;48,278,252,061bytes imply~179.85s nominal transfer. Per-FD NOREUSE remains a nonbinding hint; unavailable/rejected advice is recorded, with no cache eviction, direct-I/O fallback or faster reader. Cheap whole-deadline/cancellation checks run per chunk/pacing step; heavy resource checks run at200ms cadence. Startup300s, generation90s/max64output/onePOST/no retry, total900s including verification and recovery, reserve185s remain. Read syscalls are software-deadline checked, not an OS-enforced hard I/O kill.

## Monitoring and pressure

One locked sampler is shared across foreground, model-start/generation watchers, phase diagnostics and the local Coordinator's Runtime instance. It normally reads at5Hz, plus finite forced-fresh phase boundaries. MemAvailable/SwapTotal/SwapFree are parsed from the same meminfo text and used=total-free. GPU sysfs and boot identity join that batch. Core missing/invalid/incoherent values, boot/capacity changes, stale/failed reads, swap exhaustion or total used above the authorized cap stop admission. Zero configured swap is conservatively blocked without creating any swap. This is a monitored stop limit; no OS-wide quota is installed or imposed on other work.

RAM24GiB during asset/pre-create/start admission, activeRAM>16GiB, GPU<=58GiB, read-only/nonroot/default-seccomp/cap-drop/no-new-privileges/internal network, existing512MiB JIT and memory=memory-swap=32GiB are preserved. Positive ownership and mandatory Docker OOMKilled state are checked. A known owned OOM/cgroupOOM event aborts generation. Detailed cgroup current/peak/pressure and JIT measurements remain optional diagnostics: absent data is UNAVAILABLE, notzero. The native hasher's RSS/swap/CPU/I/O/faults and inherited cgroup are recorded separately; its inherited group is not assumed exclusive.

PSI and swap-I/O are still recorded, but the earlier proposed1GiB growth cap and numerical PSI1%/10%/16MiB/s rules were **not approved and are not enabled**. Real pressure is still guarded by RAM/GPU/32GiB limits, OOM state, deadlines and mandatory core-monitor validity. No assertion that high swap alone identifies target OOM or that current limits guarantee capacity is made.

The host baseline remains fixed under the common lock for audit; it does not add8GB to the user's absolute limit. Physical samples, logical checks and probe CPU/wall time are separately recorded. New resource-policy/summary artifacts identify the absolute8GB rule and its actual-capacity clamp; inherited128MiB/zero-growth claims are removed only from the new run. Old summaries are never rewritten.

## Cleanup and recovery

Pressure and OOM aborts cannot block positively owned cleanup; ownership/CID checks remain mandatory during release. The only patched lifecycle threshold is this local Coordinator Runtime object, not shared services or other model profiles. Recovery rechecks current resource eligibility under the8GB total cap before reloading30B. If the cap/pressure/monitor conditions still fail after cleanup, restoration can remain BLOCKED/UNKNOWN with evidence; the cap is never relaxed to claim recovery. UNKNOWN requests are not resent.

Logs and summary: `<PROJECT_ROOT>/agents/local_llm/.runtime/backend-api-trials/sglang-<run-id>/`. Saved bad samples include actual observed values or explicitNone if acquisition failed; no stale prior value is substituted. On failure inspect the single run and intent, rather than repeating the command. No model inference or host full-model hash has yet been executed by Codex for this preparation.

Validation:179offline CPU tests and independent review, covering absolute-vs-growth/GiB, min-capacity/zero-free/missing/capacity/boot change, coherent single read, shared5Hz/pacing, wrong old evidence, one allowance/onePOST, truthful policy audit, OOM cleanup, and refusal to restore while over8GB.
