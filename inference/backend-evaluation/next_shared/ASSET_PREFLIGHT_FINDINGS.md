# SGLang sequential-loader preflight result

## Confirmed terminal evidence

Run `sglang-54b722c61d324f34b20bad1f2efb75d6` stopped at21.534seconds during full-SHA asset verification. Environment NOT_RUN, quality UNASSESSED,30B unload/container create/start/generation intents all absent. Cleanup confirmed; restoration NOT_NEEDED. The single GPU attempt marker for operator9f3d6953c389d9bca94020de8b8cdbcaedd4580d458cd78dda57af8073338d96 is absent. Its source-preflight intent exists and stays preserved; shared UNCERTAIN is absent. Do not delete the intent or rerun the old wrapper blindly.

The fixed-image CPU capture and structural loader-option gate succeeded. Exact receipt SHA256:5f95ce6ca4620bf091b31d6cc5b2a1c7539d04211af96367a7f59eda74b6e7ba. Receipt confirms CPU-container absence, fixed be68image, selected four source hashes and no backend/source execution. Re-running the installed AST gate on that saved receipt succeeded. This evidence may be reused for this exact immutable image with a fresh host image-ID check; it is not reusable for a changed image, and does not replace model-asset verification.

## Paging and attribution

Host swap baseline156,987,392 ->292,929,536bytes, net135,942,144 exceeds134,217,728. First-failure MemAvailable51,824,664,576bytes/GPU22,766,051,328bytes. The retained~21.1s telemetry interval shows121,905,152bytes swap-out,0swap-in, PSIavg10 max0.18. No target process existed, so owned cgroup/JITtelemetry sample_count0 is expected.

Buffered full-file hashing is itself a substantial page-cache workload, so it is a plausible contributor. The current logs do not record per-file/read-byte progress or host process/cgroup attribution; they cannot prove it caused the paging. Swap growth is a conservative host admission condition, not proof that this model exhausted memory. Codex's PID view contains PID1=codex and only3visible user processes; it cannot inspect the host's other applications through that view. Subsequent1.1s stable global counters only describe that later interval.

Linux file reads normally use page cache: https://www.kernel.org/doc/html/latest/mm/page_cache.html

## Minimal next decision

1. Keep the original GPU allowance unused, preserve the failed run and source intent, and use an explicit evidence-bound continuation rather than deleting/reissuing them. Reuse the exact successful static receipt; no repeat CPU image capture is needed.
2. Keep fresh full SHA256 for all20model files. The historical acquisition records hash/size but lack a complete persisted inode/mtime/ctime identity binding; metadata-only checks are not equivalent to fresh cryptographic verification.
3. Candidate reader:1MiB application buffer;256MiB/s paced aggregate reads;240s total asset-phase deadline across all files. This is about179.9s nominal transfer time for48,278,252,061bytes, with900s overall budget unchanged.240+300startup+90generation+185recovery=815s before other overhead. Resource checks continue during pacing. No fallback to a faster reader on failure.
4. Request only POSIX_FADV_NOREUSE on each opened read-only model descriptor, with Linux>=6.3/support checks. This is a nonbinding access-pattern hint, not cache eviction, cache bypass or a guarantee of lower paging. Do not use DONTNEED, WILLNEED, O_DIRECT, global drop_caches, swap clearing or host-setting changes. Unsupported/rejected advice stops this candidate explicitly.
5. Preserve the existing fixed resource baseline before asset verification and128MiB net-growth limit through the trial; do not reset it after hashing. If this lower-impact preflight still exceeds the limit, report PREFLIGHT_RESOURCE_ABORT/NOT_RUN and stop. Model loading/generation remain untested.
6. Persist phase/file/bytes-read/timing plus aligned global counter snapshots at asset-start/completion and model-lifecycle boundaries. Keep host aggregate observations distinct from positively owned process/cgroup measurements. No prior missing values may be reconstructed as fact.

NOREUSE semantics and nonbinding behavior: https://man7.org/linux/man-pages/man2/posix_fadvise.2.html

## Prepared versus executed

A staged candidate reader and9fixture tests cover all20hashes, unaligned file tail, wrong digest, file replacement, unsupported hint, cancellation while pacing and whole-phase deadline. Hints were mocked; no model bytes were hashed by Codex and no advice was applied to model files. The candidate is not installed or integrated into the host launcher. No new trial/resume command is issued here. Existing host settings, processes, thresholds, markers and original evidence were unchanged.


## Subsequent continuation integration

The parent authorized the bounded-reader integration under the existing unused GPU allowance. The new source-pinned host launcher and evidence-bound continuation are installed; see ASSET_RESUME_RUN.md. NOREUSE unavailable/rejected is now explicitly recorded without replacing advice or removing pacing/guards. This supersedes the earlier candidate-only stop-on-unsupported proposal. No continuation or model operation has yet started.
