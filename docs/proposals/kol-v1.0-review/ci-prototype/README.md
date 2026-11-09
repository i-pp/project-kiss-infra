# KOL v1.0 license governance CI prototype

**Draft, isolated, and not adopted.** This package does not license or relicense any existing project. The license files under `examples/` are synthetic placeholders, not legal grants. `LicenseRef-KOL-v1.0` is a local SPDX-style identifier, not a registered SPDX license or an OSI/FSF approval.

## Run the complete fixture check

Requirements: Python 3.10 or later and its standard library. No installation, container, network, credentials, or account changes are needed. From this package directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tools/license_guard.py check \
  --root examples/fixture-repository \
  --policy examples/fixture-repository/policy.json \
  --baseline examples/trusted-baseline.json \
  --candidate-baseline baseline.json \
  --artifact examples/fixture-aceis.zip --artifact-kind aceis
```

Expected: all unit tests pass, then a JSON report with `"status": "pass"`. Exit 0 means these declared mechanical checks passed. Exit 1 means a violation. Exit 2 means invalid input, unsupported policy, or an inspection error. None means legal approval.

The commands inspect synthetic source, original third-party notices, a preserved legacy source file, pure generated output, and a packaged fixture. They do not run AceIS or acc. See `docs/CI-REVIEW.md` for verification and open integration work.

## What the prototype checks

- Every repository file except `.git` metadata must be an explicitly protected document, a scoped source/input, or a reviewed exclusion with a reason. New file extensions cannot bypass inspection. Symlinks fail instead of being followed.
- Each source/input belongs to exactly one rights scope. Licensed sources must carry the exact configured SPDX expression and the recorded actual copyright holders. Compound AND/OR expressions are supported against an explicit identifier-to-document map. SPDX WITH exceptions require further implementation and are rejected.
- Existing SPDX expressions, rights classifications, and copyright statements cannot silently disappear or change. Additional contributors can be added to first-party files. Existing legacy/vendor source is conservatively protected byte-for-byte, including non-SPDX permission/restriction prose, until an explicit rights review approves an update.
- Legal documents, NOTICE facts, rights-evidence records, and selected governance files are hashed. The actual executed policy is independently bound into the trusted baseline by canonical JSON hash. Replacing the CLI policy cannot bypass that binding.
- Third-party and runtime-bearing scopes retain their own documents. Third-party code cannot be labeled KOL by this policy. Unknown rights must use quarantine and fail the gate. Git history, package metadata, labels, and an owner's account access do not establish copyright permission.
- Distribution directories, ZIPs, and TARs require exact license/notice bytes, a declared inventory of every payload member, and explicit source-scope provenance. Included components automatically add their original licenses and notices even if `bundled_in` was omitted. Undeclared members fail. Path traversal, duplicate file members, links, special TAR members, and oversized content fail. Archives are never extracted.
- Pure acc output carries no compiler-credit or KOL requirement. An independently chosen user license is supported, including voluntarily chosen KOL with explicit user-choice provenance. No-license pure output can omit license documents. An explicitly selected output license requires its corresponding document. Runtime/third-party material cannot be silently placed in the pure-output class. Mandatory compiler-credit and unexpected KOL markers are checked in text and binary output payloads.

The marker checks are conservative regression checks, not a proof that every natural-language obligation or embedded runtime has been discovered. They may require human review of false positives. Never remove a notice automatically in response to a failure.

## Policy and rights records

`examples/fixture-repository/policy.json` is the runnable schema example. Paths are literal repo-relative POSIX paths or directory prefixes; they are not globs. Overlapping or stale source scopes fail. Relative paths containing traversal, backslashes, drive syntax, or links are not accepted. Each declared document is checked for nonempty content.

The scope kinds are:

- `first-party`: newly reviewed code under its explicitly recorded holder and license.
- `third-party`: original external license and notices, protected from silent relabeling.
- `legacy`: existing source whose bytes and existing rights information are frozen pending a separately reviewed change.
- `quarantine`: unresolved rights, never eligible for a passing release gate.
- `acc-output`: pure user output, independent from the compiler's license.
- `runtime-output`: output containing covered runtime/template material, with separately recorded documents.

Every scope links a rights-evidence file with `fixture-only`, `owner-reviewed`, or `unresolved` status. `fixture-only` is used only for this isolated demonstration. The tool pins the evidence record but cannot verify that a reviewer is authorized or that the record is truthful. Real deployment requires an authorized owner/legal review of provenance, actual holders, contributor grants, external terms, and artifact components. Unknown rights remain quarantined.

`distribution` maps required documents from source paths to package paths. `artifact_payloads` separately maps each payload path to its component scopes. Optional `source` must refer to an inspected, nonexcluded source in exactly the declared scope and requires an exact copy of that output; compiled binaries need verified build provenance in addition to this declared inventory. A `source` path does not itself prove which compiler/runtime produced a binary.

The `aceis` distribution must include the mapped KOL document and configured attribution notices. The `acc-pure-output` class permits only pure-output scopes. Document mappings in that class are the user's independently chosen documents, not an acc-imposed license. UI/manual AceIS credit is not checked or required.

## Preserve a trusted baseline

`inventory` prints the observed machine-readable inventory and violations without modifying files:

```sh
python3 tools/license_guard.py inventory \
  --root examples/fixture-repository \
  --policy examples/fixture-repository/policy.json
```

`snapshot` prints a candidate baseline only for a mechanically compliant tree. Creating a baseline does not approve legal terms or ownership. Review it separately and store the trusted copy outside the candidate-controlled change. Do not solve a failure by regenerating and accepting the baseline in the same PR.

```sh
python3 tools/license_guard.py snapshot \
  --root examples/fixture-repository \
  --policy examples/fixture-repository/policy.json > /tmp/kol-candidate-baseline.json
```

`check` compares the candidate's baseline file with the supplied trusted copy byte-for-byte. It also compares the current tree and executed policy against that trusted copy. The candidate baseline path must be a documented exclusion because its own bytes cannot be hashed into itself.

A malicious caller can supply an entirely fabricated trusted baseline and checker. The trust source must be enforced by CI outside the candidate's control. `workflow-templates/license-governance.yml.disabled` demonstrates a read-only, trusted-base fixture check and is deliberately inactive. It is not a complete production release workflow. It neither builds real distributions nor configures repository rulesets, approvals, or releases. Owner approval and a trusted required-workflow/ruleset are prerequisites before activation.

## Print a header for new code

Use the actual verified rights holder, not an assumed organization:

```sh
python3 tools/license_guard.py header \
  --holder 'Actual Verified Rights Holder' --year 2026 --style c
```

This prints the two standard header lines to stdout only. The hash-comment style is available with `--style hash`. Apply the template only to new, approved in-scope code after adoption. The tool has no bulk-header rewrite or existing-file update command.

## Current repository constraints

Read-only inspection found no established license grant in the sampled Project-KISS/infra files; empty AceIS component repositories provide no source rights evidence. External NPU packaging includes an explicit discrepancy between MIT metadata and vendor EULA/notice conditions. These observations are migration blockers, not reasons to infer permission or impose KOL. The parent scope report contains commit-specific evidence and the review plan.

The workflow is not enabled, no real repository was modified, no branch or PR was pushed, no license term was adopted, and no public release occurred. Source implementation rights and the legal candidate must be reviewed before integrating this prototype into an actual distribution.
