# LAF integrated source: current delivery plan

## Busy-reader summary

The local delivery branch combines previously reviewed model management, the
opt-in Core and host supervisor, the permission-fixed source-image builder and
the hardened CLI response parser. It does not replace any running service.

From the checkout root, Python 3.10 or later:

```sh
python3 -B scripts/check-laf-delivery.py --suite portable
python3 -B -m inference.local_platform.cli --help
python3 -B -m inference.local_platform.cli model --help
python3 -B -m inference.local_platform.cli model catalog
```

The software check uses only repository-owned Python unit/mocked tests, temporary
files and fake subprocesses. It does not contact Docker or real models. Portable
mode omits exactly 39 private-socket test IDs and reports each as unexecuted for
that run. A new test in the same class is not automatically excluded. It cannot
claim a full Python regression pass. Native NPU/runtime checks are separate.

On an executor where private Unix sockets are permitted, the complete integrated
Python suite can be requested explicitly:

```sh
python3 -B scripts/check-laf-delivery.py --suite full
```

The first integration attempt ran all 430 then-existing Python tests: 391 passed,
39 returned environmental PermissionError while creating private sockets, with
zero assertion failures and no skips. Those errors remain recorded. After the
Owner changed access and restarted the app, an independent private-socket check
passed. The corrected frozen 39-test run then passed, followed by the complete
457-test integrated Python suite with zero failures, errors, skips or omissions.
The exact tested source was 13e93aa. Independent evidence review verified all
457 unique IDs and all 67 recorded source/test fingerprints against that commit.

The same source also passed its offline Core image build and bounded UID1000
readability/hash/import gate for all ten allowlisted Python files. The local
image ID is sha256:8316685e60ee98c6aa02673eb7653fd4aa98c623496e8d911ef98941463ba70e.
This gate used no model/device mounts and did not operate any live service.
It checks source packaging, not actual model execution or redistribution rights.
See release/laf-integration-verification.json for the separate result scopes.

These commands are a complete software-test path for this source increment,
not a runtime Quick Start, clean-host installation procedure or release approval.

## Source integration and evidence

The private delivery branch is based on fetched main e7bd7ec. Earlier local
preparation began at 4423151 and imported the existing NPU source from 09321a0;
that source is already present on main. The earlier SSH/API access failures are
preserved as history. After the Owner changed access and restarted the app,
read-only SSH access and fetch succeeded. No SSH, network, credential or security
setting was changed by this delivery work. Original local branches are retained.

`release/laf-local-integration.json` identifies the imported increments and bytes.
`release/laf-historical-v2-readiness.json` is historical provenance for the old
e7bd7ec candidate only. Its inventory is deliberately not a current-tree release
gate. The new check fingerprints all integrated Python source and test files;
it does not establish trusted provenance, legal clearance or a complete SBOM.

The two acceptance runner modules are historical EVO-X3 harnesses bound to old
source paths and existing assets. Their mocked tests are included here. Their
plan/execute commands must not be used to claim acceptance of this integrated
tree. Adapting them requires a separate source-boundary and technical review.

## P0 and release gates

- Preserve existing Flash residency, large-model exclusion, physical release
  barriers and separate NPU failure handling. Core remains opt-in.
- Preserve installed-vs-loaded distinction, management scope, generation locks
  and uncertain-operation journals. Built-in installs remain blocked without
  verified source, license, revision, digest and capacity metadata.
- Complete current-tree model/container acceptance beyond the now-passed full
  Python and source-image gates. Prior two-cycle model/persistence evidence
  remains historical and was not re-run in this increment.
- Complete an actual PC-B to PC-A scoped edit/build/test E2E. Same-host evidence
  does not satisfy the physical second-PC requirement.
- Complete license/ownership, THIRD_PARTY_NOTICES, full dependency SBOM,
  security/private-information review and clean-host reproducibility.
- Obtain Owner approval for exact external content and destination before code
  push, artifact transmission, registry push or public release. Merge and
  deployment remain separate decisions.

Continue existing issue ownership: #4 model management and verified development,
#5 physical PC-A/PC-B and failure isolation, #7 distribution and public gates.
No paid provider is required by this software-test path. NPU is optional and
its current hardware evidence is mixed NPU/CPU classification, not NPU LLM
acceleration or application-accuracy acceptance.
