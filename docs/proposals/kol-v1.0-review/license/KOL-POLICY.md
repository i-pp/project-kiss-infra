# KOL licensing policy candidate

**Status: unadopted private review candidate.** This policy proposes operations after explicit Owner approval. It does not establish an existing license, relicense existing material, authorize publication, or certify legal compliance. The license text is a drafting aid for review by qualified counsel, not legal advice or a guarantee of enforceability.

## Decision and scope

KISS Open License Version 1.0 is proposed as an independently named permissive license. It is inspired by Apache-2.0, but is not Apache-2.0 and inherits no approval, compatibility determination, or ecosystem recognition from it. The exact interim identifier is `LicenseRef-KOL-v1.0`, a project-defined SPDX license reference, not a registered SPDX License List identifier. Do not use `Apache-2.0` to identify KOL. No OSI or FSF assessment is represented.

The proposed terms permit commercial use, private changes, binary-only redistribution, and proprietary integration without a source-publication requirement. Distribution of AceIS material requires origin credit in a supplied NOTICE or license document. Screen and manual credits are recommendations, not conditions. Tool use alone does not put acc output under KOL; copied material needs its own review.

Project-KISS remains the documentation and policy home. AceIS and designated implementation repositories remain the home of implementation material. A policy document cannot substitute for a rightsholder's grant or a file-by-file scope decision. Do not infer that Project-KISS documents, historical sources, or any existing compiler code are KOL merely because they are in a related project.

## Approval gates

Keep three decisions separate and record each explicitly:

1. **Adopt the license text.** Owner approves a specific reviewed English text, its SHA-256 digest, version, steward, and Japanese reference status after legal and editorial review. This does not apply it to code or publish it.
2. **Apply the license to identified material.** Owner approves exact repositories, source revisions, paths, ownership evidence, exclusions, contribution permissions, and effective release. Approval from every necessary rightsholder, or other sufficient authority, must be verified. Owner status alone is not proof of rights in all contributions.
3. **Publish.** Owner approves the public destination and reviewed content. A draft branch, PR in a public repository, release, website, issue, SPDX request, or OSI submission is publication and needs that approval.

For each gate, retain the approver, dated decision, exact artifact/revision, scope, unresolved conditions, and linked rights evidence. No step in this pack executes a gate. Do not apply headers, replace an operative LICENSE, change package license metadata, push, or create a public PR as a side effect of reviewing the proposal.

## Files after an approved adoption

The following is a proposed layout, not a declaration that these paths now exist in a repository:

- `LICENSE-KOL-v1.0`: the exact approved English instrument.
- `LICENSES/LicenseRef-KOL-v1.0.txt`: the same approved instrument for tooling that resolves LicenseRef references by local path. Both copies must match byte for byte.
- `KOL-v1-JA.md`: a clearly labeled non-authoritative Japanese reference.
- `KOL-POLICY.md`: governance, scope, and approval records or links.
- `ACEIS-NOTICE.md`: human-readable attribution rules and template guidance.
- `NOTICE`: actual distribution-specific required notices, separate from policy prose.
- `ACC-OUTPUT-POLICY.md`, `CONTRIBUTOR-POLICY.md`, and `THIRD-PARTY-POLICY.md`: operational guidance that does not modify the instrument.
- A reviewed file-scope and third-party inventory, with explicit handling of generated files, fixtures, documents, dependencies, and files without inline-comment syntax.

The draft English file has review metadata and BEGIN/END markers. It must not be copied verbatim into the operative license path. At adoption, a separately approved extraction of the proposed instrument is required. Freeze and hash that final text and synchronize both license locations. Never silently edit an adopted v1.0 text under the same identifier.

## Copyright and source headers

Use actual rightsholders and supported years, preserving existing notices. The requested header form for a file actually owned by I-plusplus Inc. is:

```cpp
// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1.0
```

This is a conditional template, not a finding that I-plusplus Inc. owns any file. Do not stamp it onto contributor-owned, mixed-origin, third-party, pre-existing, or generated material without the corresponding rights and scope decision. Add multiple accurate copyright lines where appropriate; do not erase upstream lines. Use comment syntax suitable for the language while keeping project-maintained source ASCII-only. For files that cannot contain comments, use a reviewed adjacent metadata file or manifest supported by the chosen tooling.

A header is metadata, not proof of title, consent, or compatibility. Do not choose `OR` to suggest a license choice unless the rightsholder has granted that choice. Do not mechanically add `AND` to mixed files as a substitute for determining which terms govern which portions. A local LicenseRef must resolve to the exact approved text, and SBOMs must include the extracted text or a supported reference to it.

## Release procedure

1. Resolve the Owner gates and legal decisions in `review/OWNER-DECISIONS.md`.
2. Confirm the exact source commit, file scope, rights evidence, third-party inventory, and compiler runtime/template inventory.
3. Verify headers and license expressions against that scope. Treat unclassified paths, missing rights evidence, and unresolved licenses as blockers rather than exclusions.
4. Assemble each actual source archive, binary archive, package, container image, installer, and downloadable runtime. Inspect the bytes recipients receive, not only the repository tree.
5. Verify the approved license text, AceIS credit, retained notices, modification record, and all component-specific obligations in each artifact. No source-publication duty under KOL excuses source delivery required by another component's terms.
6. Run technical validation and an independent editorial/legal-scope review. A metadata CI pass establishes neither ownership nor license compatibility.
7. Owner reviews the final artifacts and their digests before a separately authorized publication. Preserve the decision and evidence alongside the release record.

For an internal-only deployment or a network service without distribution, do not invent KOL publication duties. Still review copying, deployment, and separate dependencies; other licenses may have obligations triggered by network use or other conditions. Establish the actual delivery facts before concluding that a service does or does not distribute material.

## Versioning and incident handling

A correction that changes legal meaning requires a new approved license version and separate scope decisions. Do not add an unrequested “or later” grant. Keep old license texts and release notices available for existing releases; replacing a file on the default branch does not erase rights already granted.

If a rights or attribution problem is discovered, preserve evidence, identify affected artifacts and recipients, and alert Owner. Prepare a remediation proposal, but do not unilaterally send accusations, accept liability, revoke permissions, delete evidence, or replace published assets. The license candidate specifies patent termination but does not establish a notice-and-cure process for other breaches; counsel must resolve that before adoption.

## Sources and limits

- [Apache license reuse guidance](https://www.apache.org/foundation/license-faq.html#mod-license) distinguishes a changed, independently named license from Apache itself and recommends legal review.
- [SPDX license expressions](https://spdx.github.io/spdx-spec/v2.3.1/SPDX-license-expressions/) permit user-defined LicenseRef identifiers. An identifier alone does not register or approve a license.
- [OSI review process](https://opensource.org/licenses/review-process) is a separate public process. No submission or assessment is made by this pack.
