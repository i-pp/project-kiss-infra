# LAF model management: offline-tested first slice

## Busy-reader summary

This increment adds catalog, install, list, remove and storage status to the
existing stdlib CLI. It does not replace the Router or load a model. The bundled
catalog preserves `flash`, `coder-next` and `gpt-oss-120b`, but deliberately leaves
unverified provenance, versions, capacity and hashes empty. Those entries cannot
be installed until a user supplies verified metadata.

Run these safe, local checks from the repository root:

```sh
python3 -B -m inference.local_platform.cli model catalog
python3 -B -m inference.local_platform.cli model list
python3 -B -m inference.local_platform.cli model status
python3 -B -m unittest -v inference.local_platform.test_models
python3 -B scripts/check-laf-offline.py --suite portable
```

The implementation uses the existing module entry point. A packaged `laf`
executable, engine provisioning and complete Docker Compose installation remain
separate work. These commands are not a complete Quick Start for a running LAF.
The existing `status` command still queries the private Router and now includes
an independent local `model_storage` summary. Use `LAF_MODEL_STATE_DIR` to select
the same registry used by model operations; otherwise it reads
`~/.local/state/laf-models`. Catalog, list and local model status do not create directories or contact
Ollama. The opt-in inspect command makes GET-only requests to configured Ollama. Registry entries describe the last verified installation, not a fresh
engine inventory. `loaded_state: not_queried` must not be read as “unloaded.”

## What is implemented

- Strict, bounded catalog metadata: ID, engine, exact tagged reference, source,
  license and license URL, version, capacity estimate, engine manifest SHA-256,
  and a user license/authentication setup requirement.
- Ollama's existing management APIs: `GET /api/tags`, `GET /api/ps`,
  `POST /api/pull` with streaming disabled and `DELETE /api/delete`.
  Bare hexadecimal wire digests are normalized to `sha256:<hex>` in the registry.
- Separate persistent private JSON registry, bounded operation history, atomic
  replacement and fsync. Directory creation is also synced before a mutation.
- Nonblocking operation lock and the existing Router lifetime generation lock.
  An active Router or any loaded model blocks install/remove. Nothing is stopped,
  unloaded, restarted or migrated to make management work.
- Durable write-ahead pending journal. An uncertain engine outcome or digest
  mismatch leaves the pending operation in place and blocks later mutations.
  No pull/delete retry or automatic cleanup is attempted.
- Removal only of models previously installed by this registry, with the same
  engine scope and digest and no loaded models. A matching preexisting unmanaged
  model is refused rather than adopted or later deleted.
- Registry binding to numeric-loopback engine identity, model-store path and
  generation-lock path. Changing that scope does not confer deletion rights on
  another engine. Endpoint identity is not a cryptographic server identity.
- No Docker socket, Docker commands, new listener, credentials, shell commands,
  inference calls or license acceptance in this module.

All three compatibility profile IDs remain available in the Router. This module
only implements an Ollama mutation adapter. Strata/Flash installation remains
blocked until its artifact format and provenance contract are verified. The
existing Flash residency, large-model exclusion and physical resource-release
barriers are unchanged.

## Operator-supplied inputs for a future live acceptance

Do not copy the following placeholders into a production config and claim setup
is complete. No live install/remove was performed for this increment.

Both catalog and configuration must be regular owner-only files (`0600`) inside
an owner-only directory (`0700`), with no symlink or hardlink aliases. The selected
model-store directory must already exist and be owner-only. The state directory's
parent must already exist; the state directory can be created privately on first
mutation. The generation lock must already be the exact existing Router lock;
this code never creates it or changes its mode.

A configuration has exactly these fields:

```json
{
  "state_dir": "/OWNER_CONTROLLED_PERSISTENT_STATE/laf-models",
  "model_store": "/EXISTING_PERSISTENT_OLLAMA_STORE",
  "generation_lock": "/EXISTING_ROUTER_RUNTIME/generation.lock",
  "engine_url": "http://127.0.0.1:11434"
}
```

Only explicit numeric loopback HTTP endpoints and ports are accepted. There is
no proxy, redirect following, DNS hostname, remote transport or default engine
endpoint. The code does not discover the current host Docker container address
or start an engine. This protects existing service boundaries; it also means the
current Router-owned internal Docker endpoint is not automatically usable here.
An independently reviewed managed-engine/container control boundary is still
needed for that integration.

The operator must verify that the selected Ollama server's actual `OLLAMA_MODELS`
store is backed by the named persistent storage, and that registry state is also
on persistent storage. `model_store` is used for a free-space preflight; an HTTP
client cannot prove the server's filesystem mapping. This increment does not
claim verified model-volume persistence or clean-host/container acceptance.
The capacity number is a preflight estimate, not a hard engine download quota.

A private catalog is a JSON array. Each entry has exactly these keys:

```json
{
  "id": "USER_CHOSEN_PROFILE",
  "engine": "ollama",
  "reference": "OWNER/MODEL:EXACT_TAG",
  "source": "https://OFFICIAL_MODEL_SOURCE",
  "license": "VERIFIED_LICENSE_IDENTIFIER",
  "license_url": "https://OFFICIAL_MODEL_LICENSE",
  "version": "VERIFIED_VERSION",
  "required_bytes": 1,
  "digest": "sha256:REPLACE_WITH_64_VERIFIED_LOWERCASE_HEX_DIGITS",
  "user_setup_required": true
}
```

The placeholders are intentionally invalid and the size is not a model estimate.
Do not invent a digest, license or capacity from the model's marketing name.
`digest` is the Ollama manifest digest, not necessarily the SHA-256 of one weight
file. Distinct IDs cannot alias the same engine reference. Explicit Ollama tags
are required; the expected digest detects content changes behind a mutable tag.

If explicit license acceptance or authentication is necessary, the user must
complete it directly through the provider's official interface. LAF does not
perform or bypass it. `user_setup_required: true` always blocks install. A catalog
entry with `false` is an operator declaration that required user steps are
complete or not required; it is not legal verification by this code.

Only after those inputs and the storage mapping are verified, and no service or
user workload holds the existing generation lock, the relevant command shapes
are:

```sh
python3 -B -m inference.local_platform.cli model --catalog /PRIVATE/catalog.json --config /PRIVATE/config.json install MODEL_ID
python3 -B -m inference.local_platform.cli model --config /PRIVATE/config.json list
python3 -B -m inference.local_platform.cli model --config /PRIVATE/config.json status
python3 -B -m inference.local_platform.cli model --config /PRIVATE/config.json remove MODEL_ID
```

Remove is destructive to the named managed engine model. It never deletes the
source catalog or directly traverses/removes model files. Do not run these live
mutation examples against existing user models merely to test the code.

If an operation reports uncertainty, first inspect engine inventory and the
private pending journal without retrying the mutation. Recovery/reconciliation
needs an explicit follow-up implementation or a carefully reviewed operator
procedure. Deleting the journal to force a replay is not a supported recovery
method.

## Verification and remaining acceptance

The tests were written before implementation. The initial run failed because the
module did not exist. Further failing regressions captured review findings before
the fixes: real Ollama wire digests, explicit tags, engine-scope ownership and
first-directory durability. Test fixtures use official API response shapes:

- <https://docs.ollama.com/api/tags>
- <https://docs.ollama.com/api/ps>
- <https://docs.ollama.com/api/pull>
- <https://docs.ollama.com/api/delete>

V1 offline evidence: 35 model tests passed; the portable aggregate passed
231 selected checks. Its 29 private-socket tests remain explicitly unexecuted.
This is not a full regression pass. Independent review is recorded with the
artifact. No live model download/deletion, engine interoperability, machine-crash
test, volume-remount test, Docker build, hardware use, clean-host setup, publication
or deployment is claimed. Unit/mocked success is not P0 completion.

Follow-up work under existing model-management/container Issues #4/#7:

1. Curate model source/license/version/size/manifest digests from actual evidence.
2. Integrate the existing private engine through a reviewed container-management
   boundary without granting a default Docker socket or loosening network access.
3. Verify actual Ollama store/registry persistence across container replacement.
4. Add explicit uncertain-operation reconciliation without unsafe replay.
5. Validate Strata artifact management before adding a mutation adapter.
6. Run owner-authorized live lifecycle acceptance around existing workloads, then
   clean-host and PC-A/PC-B E2E gates. Publication and push need separate approval.

## V2: non-mutating engine inspection

V2 adds a GET-only observation path, using the same explicit private configuration:

```sh
python3 -B -m inference.local_platform.cli model --catalog /PRIVATE/catalog.json --config /PRIVATE/config.json inspect MODEL_ID
```

This requests only `/api/tags` and `/api/ps`. It does not create registry state,
acquire the generation lock, download, delete, load, unload, generate, log in or
accept legal terms. It can observe an engine while the Router's generation lock
is held. A CLI-level mock test verifies exactly the two GETs while that lock is
held, and verifies that no state directory is created.

`installed` and `loaded` describe the returned engine inventories for the exact
catalog reference. `digest_matches` compares the observed engine manifest with
the catalog's expected manifest digest. It is null if either comparison input is
unavailable. `registry_record_matches` describes saved registry ownership within
the configured engine scope. `managed` additionally requires an observed model
with the saved digest, so changed or missing engine content is not reported as
currently managed. This inspection never creates ownership.

An inventory result does not establish model compatibility, current weight-file
hashes or the actual engine store's volume mapping. The output explicitly labels
those checks as not evaluated, not recomputed and not verified. The two GETs are
separate observations, not an atomic engine snapshot; other authorized clients
can change engine state between them.

Two real read-only legacy LAF MCP profile-status calls observed the existing
Coder Next and GPT-OSS120B assets as present with saved sizes matching, while both
legacy routes returned `UNAVAILABLE / TRANSPORT_ERROR`. Neither call recomputed
full model SHA256 and neither generated or loaded a model. This is not a direct
probe of the newer private Router, and must not be called proof that it is down.
The mocked CLI flow and these real read-only status observations are distinct
checks, not real engine lifecycle/E2E acceptance.

## Curated historical provenance register

The separate [historical evidence register](../inference/local_platform/model-provenance.json)
records the exact preserved comparison SHA256 and reported asset revisions:

- Flash GSQ-RCO Q2_0: `ed59f92082b1e93c0e96d60a8b11aab089b52f09`.
- Coder Next Q4_K_M: `b82fb7382639d97b38fa7672e526c760c2fb358e`.
- GPT-OSS120B MXFP4: `7200b74bea78b0a2964ef9f3897eefa401e890ff`.

The preserved cloud comparison and the original EVO-X3 comparison were verified
byte-for-byte using SHA256
`e22500a7c31f7e2f8b76c951348a135a535d7fd5013f7206059c904e99696644`.
The pinned Flash/Next source-review JSONs were also checked, but they review
candidate code and diagnostic prose, not model acquisition provenance. A matching
report hash establishes which report was read. It is not a current model-weight
verification or independent proof of the model's upstream identity.

The register deliberately leaves verified acquisition URLs, license evidence,
weight hashes/bytes and engine manifest digests empty. The AWQ4 model revision is
not transferred to Q4_K_M. Runtime image/executable identities remain explicitly
separate from model-weight and engine-manifest identities. No entry is marked
installable, and this register does not change the built-in catalog's blocks.

Read-only discovery of the exact existing Router user-unit and config identified
the expected configured Ollama store. Neither expected custom model manifest was
present, and a metadata-only manifest-directory listing returned no files. No
blob was read or rehashed. This does not establish service health or explain the
absence. It leaves an actual provenance gap rather than permission to substitute
an image digest, revision string or similarly named model.

A complete installable catalog still needs evidence for the exact chosen artifact,
its license and any user-required steps, per-file identity/size, Ollama manifest
identity, compatible engine packaging and persistent store/capacity. The current
research can pin historical evidence; it cannot truthfully supply those missing
facts or claim a new compatibility test.


A separate direct Router check used the config-backed private socket after owner,
directory0700 and socket0600 checks. Exactly one GET `/health`, with no retry,
returned HTTP200, `status: ready` and NPU `ready`. Read-only service metadata was
active/running with success. GPU fields were not extracted from that response;
no absent top-level value is interpreted as false or unloaded. This establishes
current Router readiness only and does not establish inference or lifecycle
acceptance. It is separate from the legacy MCP transport error above.

V2 offline evidence: 43 focused model tests pass, including six new GET-only/stale
inventory tests and two provenance-register invariants. The portable aggregate
passes 239 selected checks, with the same 29 socket tests explicitly unexecuted.
The model inspection code passed independent review. The original V1 artifact is
preserved unchanged; V2 is a separate incremental artifact. No download, model
removal, load/unload, service change, source push, publication or deployment was
performed.
