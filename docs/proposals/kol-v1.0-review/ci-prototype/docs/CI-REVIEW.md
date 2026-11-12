# CI verification and integration review

## Verified locally

The prototype uses Python's standard library. The complete fixture suite covers valid and invalid SPDX headers, copyright preservation and contributor additions, legacy/vendor content drift, required NOTICE facts, protected document and evidence hashes, alternate-policy bypass attempts, candidate-baseline tampering, unknown and overlapping scopes, unknown extensions and extensionless files, quarantine, artifact inventories, source-copy equality, mandatory component notices, pure-output independence and voluntary user licenses, runtime non-exemption, archive traversal/links/duplicates, binary marker scanning, and stdout-only header generation.

Independent technical review reproduced five initial gaps: non-SPDX legacy prose removal, alternate policy invocation, undeclared artifact members, inconsistent voluntary KOL output handling, and unknown source extensions. Regression tests were added and all five fixes are present. A second review found excluded payload sources, missing selected-output license documents and overbroad document exemptions; these were also fixed and regression-tested. The verification JSON records the actual results; verbose execution logs remain local under repository policy. A final independent technical review reran all 74 tests, reproduced the corrected failure cases, and accepted the isolated prototype with no blocking finding within its stated scope.

## Not verified or enabled

- No GitHub-hosted job has run. The `.yml.disabled` template is inactive and assumes a future `license-governance/` destination.
- No real AceIS/acc compiler, linker, runtime, container, installer, wheel, or release artifact has been built or inspected by this prototype.
- No dependency resolver, lockfile/SBOM reconciliation, dependency license compatibility review, contributor-title validation, or proof of binary provenance is implemented.
- Regex/header and marker inspection is deliberately bounded. It cannot determine authorship, legal sufficiency, compatibility, the meaning of arbitrary natural language, or whether binary code was copied from an undisclosed source.
- Per-file input size is 16 MiB and artifact total is 128 MiB. These are bounded prototype limits, not silently ignored coverage. Oversized inputs fail.
- Plain-file and source headers use UTF-8. Archive paths must be canonical relative POSIX names. TARs rooted at `./` are rejected; package canonical member paths instead.
- Legacy/vendor changes are conservatively frozen in full, so an otherwise benign update needs explicit review and a trusted baseline change.

## Activation gates

1. Owner selects the real candidate license text and approves adoption scope after legal review. The temporary `LicenseRef-KOL-v1.0` remains unregistered unless SPDX independently accepts a registration.
2. Inventory actual repository files, copyright holders, contributor grants, pre-existing licenses and vendor notices. Put unresolved material in quarantine. Do not infer rights from Git authorship, package metadata or repository ownership.
3. Create reviewed provenance/evidence records. Decide which first-party files may be newly labeled and retain all existing third-party/legal notices. Do not apply fixture statuses to real code.
4. Replace placeholders with the independently reviewed candidate license and real NOTICE facts. Pin legal documents, governance code, policy, evidence, workflow and relevant tests in the trusted baseline.
5. Wire the gate to each actual source and binary packaging job. Produce a component inventory from the build graph/SBOM and verify each artifact member and runtime dependency. Run the gate on the final packaged bytes, not only a staging tree. Synthetic fixture success is insufficient.
6. Add real acc generation tests for default output, user-selected licenses, static/dynamic runtimes, copied templates, debug/release binary output and third-party embeddings. Verify pure output receives no compiler-credit obligation and legitimate embedded notices are preserved.
7. Require owner/legal approval for changes to licenses, notices, baselines, exceptions, evidence, policies and the checker. Use an organization required workflow or equivalent externally trusted gate so a candidate cannot remove or spoof its own check. Read-only tokens and no secrets should be used for untrusted PRs.
8. Enable the workflow only after the above approvals. Formal adoption, public PR publication and public release remain separate owner decisions.

## Provenance of operating guidance

- `i-pp/ai-orchestration/docs/ai/orchestration.md`, fetched read-only, blob `b27d0e66daefea0498165c5a23c057ebeafe7bd9`.
- `i-pp/ai-orchestration/docs/ai/policies.md`, fetched read-only, blob `0554d18499161015185e7f6fe821fd0ce4a5175d`.
- User KOL request: message `Sentinel_6008d03c80bc819180c9b3f1fef98947`, 2026-11-09. Its explicit interim identifier and approval boundaries were preserved.
