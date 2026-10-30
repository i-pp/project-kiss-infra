# Flash Q2_0: bounded first configuration proposal, not executed

Source pin: `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`. This supplement does not
authorize acquisition or execution. Downloads, imports of Strata, packing, model
loads, inference and host changes remain zero.

## Decision

Prefer a **reviewed 48 GiB process soft budget with a small explicit cache** over
claiming that a small cache makes the existing 32 GiB budget feasible. Retain the
common runner's host memory/GPU headroom gates, timeout and return-to-30B plan.
The proposed first configuration is the existing two-shard Q2_0, AVX512 pack,
MTP off, vision off, parallel 1, context 8192, `--expert-cache 1024`.
48 GiB is a monitored stopping budget, **not a proven peak requirement or changed
container/service cap**. No cap has been relaxed. The fixed arena is already
31.640625 GiB; adding dense/session/cache makes 32 GiB implausible for this default
path. No alternative mmap/resident policy is silently substituted.

## Exact cache arithmetic and remaining overhead

`--expert-cache N` accepts integer expert slots; `auto` is special. There is no
byte/GB form of this flag. The uniform Q2_0 slot is 1,382,400 bytes:

| Component | Bytes | GiB |
| --- | ---: | ---: |
| CPU expert arena: 48 x 512 x 1,382,400 | 33,973,862,400 | 31.640625 |
| GPU expert copy: 1024 x 1,382,400 | 1,415,577,600 | 1.318359375 |

This cache duplicates selected host experts. It does not replace the arena. Its
residency tables and HIP staging are additional. Source:
[pack_layer.py L2–18, L34–44](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/pack_layer.py#L2),
[cache allocation contract](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/include/strata/core/expert_cache.hpp#L84).

The upstream memory reference is ~34 GB experts plus ~6 GB other, not an EVO-X3
measurement. Dense weights use the generated `index.txt` engine pool size, which
can differ from file size because of dtype conversions. The header documents
5.305 GiB dense on disk and 1.374 GiB reduction for its referenced artifact, not
a complete fixed runtime total. Session memory is a sum of GDN state, QSA/KV,
scratch, MoE/block buffers and PLE history; KV depends on context. Prefill buffers,
HIP libraries/graphs, allocator overhead and host page cache add further memory.
Do not count UMA GPU allocations as separate physical RAM capacity. Exact peak
and fixed/KV split for this first launch remain unmeasured.

Sources: [memory table](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/DETAILS.md#L81),
[index conversion](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/pack_index.py#L11),
[session_bytes](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/core/session.cpp#L45).

## Packing disk, buffers and time

The AVX512 setup advertises **~40 GB written, 2–5 minutes**. This is an upstream
setup estimate, not a local timing or an upper bound; hashing/verification/tokenizer
and storage speed add time. No measured peak RAM or EVO-X3 pack duration was found
in these fixed files. [Setup branch](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/setup.py#L9160).

The builder writes `experts.bin`, `dense.bin`, `embd.bin` directly, then metadata
`experts.json` and `manifest.json`. It does not make a second full ~40 GB temporary
pack; shard 2 is referenced, not copied. Use a new output directory so originals
and any existing pack remain intact. `pack_index.py` adds only text `index.txt`
(header's example ~150 KB); tokenizer creates its own small files. The final
~40 GB is additional to the existing 66.4 GB input and any retained old pack.

RAM is not zero-copy: `pack_layer.py` constructs the three role arrays, interleaved
gate/up, concatenated blobs and `tobytes()` per layer. Dense conversion similarly
holds tensor intermediates. `open_shard()` uses read-only mmap, avoiding an eager
37.6 GB source read; touched pages and tensor copies still count toward pressure.
Those facts do not establish an exact RSS maximum. Reserve disk margin beyond
~40 GB and measure both preparation and launch separately.

Sources: [pack builder](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/strata_pack.py#L196),
[layer buffers](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/pack_layer.py#L59),
[index output](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/pack_index.py#L215),
[read-only mmap](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/canonical_xcheck.py#L542).

The immediate blockers remain absent GPU device nodes and an unacquired/unreviewed
engine in this Codex environment. This document is a human-reviewed deployment
proposal; it does not create a host execution route or modify protection.
