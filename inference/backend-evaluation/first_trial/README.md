# One human-reviewed Strata / Flash trial — not a launcher

This directory contains an inert proposal and portable config, not permission to
acquire or execute Strata. The software is an unrecognized source: individual
acquisition/execution review and a human-operated usable GPU host context are
still pending. No download, model load, generation, Docker operation or host change
is implemented here. The existing router's 32GiB cap stays unchanged.

Validate locally without Strata or GPU access:

```bash
python3 -B validate_first_trial.py
python3 -B -m unittest -v test_first_trial
```

The validator checks fixed scope, identities and proposed budgets only. It does
not enforce a process deadline, memory limit, disk quota or lock. Those operational
controls must be supplied and reviewed before a live trial; their values below
are proposals rather than current configuration.

## Operator handoff, after individual approval

1. Acquire the fixed source and HIP-halo archive named in `first-trial.json` through
   the reviewed official source. Inspect the archive before extraction; check its
   SHA256, signed manifest, per-file hashes, BUILD identity and third-party notices.
   Do not run an installer or an unreviewed entrypoint. Reconcile the base Qwen
   Community License 1.0 with the derived model card's Apache-2.0 metadata.
2. Inspect required Python versions/dependencies without installing them globally.
   Resolve the verified executable inside the extracted manifest to the `exe`
   placeholder. Keep source, engine, new pack, logs and existing weights separate.
   Do not execute this work through a Codex host broker or create another namespace.
3. Arrange exclusive ownership with the existing coordinator and no active/UNKNOWN
   work. Acquire/release the common lock at compatible controller boundaries; do
   not call a coordinator operation while recursively holding its same lock.
   Unload only router30B through the existing authorized model-management route;
   retain the router, original container, daemon and Tunnel. Require post-unload
   MemAvailable >=64GiB and free disk >=100GiB. Otherwise restore30B and stop.
4. Create one new output directory, with no `--force`, no integrity-check bypass,
   and monitor the proposed RAM/disk/time budgets from the JSON. The following
   command *shapes* were read in pinned upstream source; they have not been run:

```text
python <PINNED_SOURCE>/tools/strata_pack.py build --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/strata_pack.py verify --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/pack_index.py --pack <NEW_PACK_DIR>
python <PINNED_SOURCE>/tools/strata_tokenizer.py --gguf <FLASH_SHARD1> --out <NEW_PACK_DIR> --check
```

   Preserve the builder's own source-integrity validation during a future approved
   conversion. The previously completed SHA proof is reused for this proposal;
   no new SHA scan is part of the present task. Verification must pass without
   modifying source weights. The default expert verification samples every32nd
   expert per layer; record that coverage and do not claim exhaustive verification.
5. Resolve the placeholders in `strata-host-config.EXAMPLE.json` only to the
   reviewed source, manifest executable, new pack and existing two shards. Set
   `STRATA_KEEP_LEFTOVERS=1` for the owned server process so cleanup cannot target
   unrelated leftovers. The fixed server command shape is:

```text
python -m serve.server --engine strata --config <REVIEWED_CONFIG_JSON> --host 127.0.0.1 --port 8082
```

   Run from the pinned source in the human host context only. Context8192,
   prefill512, expert-cache1024 slots, MTP/vision off. No hooks or other downloads.
   Monitor the full owned process tree, system RAM and GPU; a 48GiB RSS soft stop
   is neither a hard cap nor proof that UMA/device allocations fit.
6. GET health/model status must establish loaded=true and the selected model, not
   merely HTTP200. Then one `/v1/chat/completions` request only: temperature0,
   seed42, max_tokens128 and `Reply with exactly ACEIS_STRATA_FLASH_ACK`.
   Record startup/API/answer format separately from model quality. No warmup,
   retry, B4 launch or extra generation. UNKNOWN means reconcile without resending.
7. Stop only the experiment-owned process tree (STOP/QUIT then bounded20s/5s/20s
   escalation), verify memory recovery, then load30B through the existing authorized
   coordinator and check health/identity. Do not kill other work or erase UNKNOWN.
   Do not restart Docker or recreate the original container as an automatic fallback.

Proposed pack/verify deadline1800s, startup90s, generation90s, stop45s, restore120s:
post-unload maintenance budget2145s. Software acquisition/inspection happens before
unload. Failed restore or UNKNOWN is a block requiring reconciliation, not a promise
of availability by the deadline. No live runner or monitoring controller is supplied
or executed in this preparation.

The single sanitized material card is at
`docs/material-cards/2026-10-29-strata-flash-first-trial.md` relative to the repository.
