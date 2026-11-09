# KOL v1 private draft review

This proposal brings the KOL v1.0 English candidate, Japanese reference, operating policies, Apache comparison, rights audit, v4 design patch and isolated CI prototype into one private review. Owner and qualified legal review are still required. Nothing here applies KOL to this repository or its existing code.

## Five-minute orientation

1. Read [Owner decisions](license/review/OWNER-DECISIONS.md), especially rights, general breach and cure, patent retaliation, and copied runtime material.
2. Review the complete [English instrument](license/LICENSE-KOL-v1.0), its [Japanese reference](license/KOL-v1-JA.md), and the [Apache comparison](license/APACHE-2.0-COMPARISON.md).
3. Review the [repository audit and migration proposal](audit/AUDIT-AND-MIGRATION.md). Unknown existing rights stay outside KOL application. The v4 patch is an unapplied review artifact, not a change to GitHub main.
4. Run the commands below. They exercise synthetic fixtures, not AceIS or acc.

Requirements: Python 3.10 or later and its standard library. No installation, Docker, network, credentials, model download or repository setting change is needed. From the repository root, or the extracted ZIP root:

```sh
cd docs/proposals/kol-v1.0-review
sha256sum -c MANIFEST.sha256
cd ci-prototype
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tools/license_guard.py check \
  --root examples/fixture-repository \
  --policy examples/fixture-repository/policy.json \
  --baseline examples/trusted-baseline.json \
  --candidate-baseline baseline.json \
  --artifact examples/fixture-aceis.zip --artifact-kind aceis
```

Expected: the hashes match, 74 tests pass, and the final JSON reports `"status": "pass"`. These commands are a complete check of this fixture package, not a Quick Start for a working compiler or production license gate. Windows users can run the Python commands in a Python shell environment; `sha256sum` requires a compatible shell.

## Contents

- `license/`: the seven requested texts in full, Apache comparison, drafting review, and Owner decision register. The canonical proposal remains review-marked; there is no operative KOL installation at the repository root.
- `audit/`: bounded repository findings, the proposed v4 chapter 12 and ADR patch, source digests and isolated-application results. Complete private infrastructure sources and full v4 originals are not duplicated here.
- `ci-prototype/`: standard-library-only checker, 74 regression tests, synthetic source and artifact fixtures, trusted-baseline demonstration, and an inactive workflow template.
- `review/`: integrated verification and review. Component statements such as "no external writes" describe their preparation stage before this private review delivery. They do not claim that later draft delivery is absent.

The full seven texts are `license/LICENSE-KOL-v1.0`, `license/KOL-v1-JA.md`, `license/KOL-POLICY.md`, `license/ACEIS-NOTICE.md`, `license/ACC-OUTPUT-POLICY.md`, `license/CONTRIBUTOR-POLICY.md`, and `license/THIRD-PARTY-POLICY.md`.

## Scope and approval boundaries

The only proposed repository changes are new files under `docs/proposals/kol-v1.0-review/`. Existing source files, headers, notices, documentation, branches, rights records and history are unchanged. No public repository is a delivery target. No license adoption, existing-code relicensing, merge, deployment, release or public publication is authorized by this draft.

`LicenseRef-KOL-v1.0` is a project-defined interim identifier, not an SPDX License List registration. OSI approval and an FSF free-software assessment have not been obtained. Compatibility, enforceability, ownership and complete dependency clearance are not guaranteed. A legal instrument containing draft markers must not be installed as an operative grant.

The fixture's KOL document is an explicit synthetic placeholder. It is deliberately distinct from the proposed legal text. Fixture-only rights evidence does not approve real code. The header subcommand prints a template to stdout and does not edit any source; the actual holder must be verified before use. No corporate ownership is inferred from the requested example header.

The workflow remains outside `.github/workflows` and ends in `.disabled`. It assumes a later approved `license-governance/` destination, so it must be adapted and independently trusted before activation. It does not build real distributions or enforce repository rules. Read [CI integration gates](ci-prototype/docs/CI-REVIEW.md) before proposing activation.

Three later decisions remain separate: adopting exact license text, applying it to identified material with adequate rights, and authorizing a named publication or release. Owner approval does not replace third-party permission.
