# KOL v1.0 repository audit and migration proposal

Observation date: 2026-11-09 UTC. Status: proposal only. No formal adoption, publication, repository edit, copyright reassignment, license application, or relicensing was performed.

## Decision summary

Use **KISS Open License Version 1.0 (KOL v1.0)** as the proposed formal name, **KOL-v1.0** as the version label, and **LicenseRef-KOL-v1.0** as the provisional custom SPDX-style identifier. The identifier is not an official SPDX License List entry and is not a legal grant by itself.

The legacy AceGeneralPublicLicense/AGPL name in the design is a concept, not an operative license. Replacing that name must not replace genuine GNU AGPL identifiers or upstream licenses. The repositories inspected do not establish a project-wide existing license or the rights needed to relicense existing material.

Keep all original sources and notices. Propose adoption separately, with an exact license text hash, exact repository/commit/file scope, verified rights or permission, required third-party obligations, and explicit Owner approval. Owner approval cannot substitute for another rightsholder's permission. A code scanner cannot prove ownership or legal compatibility.

## Source v4 and patch scope

Two native Space files resolve to the same filename:

- `/Project-KISS/Project-KISS_design_v4_draft.md`: polished v4, 774 lines, 66,898 bytes; SHA-256 `a99cbfb1a3d9d49f8fc9a6d379fc7ccafec5464a19c580e6ff84680e9e77fff5`; native reference `libfile_dfb44debdae88191ac2c3cb16aee9900`.
- `/Project-KISS_design_v4_draft.md`: earlier v4, 762 lines, 65,497 bytes; SHA-256 `edc44f7679fd6d8de887c60d2ad4c21ec7c37ae2190fd3a93162bdaba7a25b1c`; native reference `libfile_ac6e13b6efac81919efd3df51c980290`.

Chapter 12, lines 454–500, is identical in both. The legacy-name ADR candidate appears at line 645 in both. The source labels itself a draft and explicitly distinguishes direction, proposal and open work.

The proposed patch changes only chapter 12 and the license-related ADR candidate in chapter 17. It uses the polished copy as its working comparison baseline without designating either copy as a newly adopted canonical source. The patch:

- Records the old and new names without implying that a rename grants rights.
- Adds separate Owner approval gates for formal adoption, publication and existing-code application.
- Replaces the name-only/minimal-notice preference with preservation of existing copyright, licensing, attribution, NOTICE and disclaimer text.
- Keeps contributor records split and traceable, and adds evidence of rights and application decisions. Git authorship alone is not consent or an assignment.
- Preserves original licenses for third-party material and isolates material whose rights are unknown.
- Distinguishes tools, linked runtimes, headers, generated outputs, models and data. Package labels alone are insufficient.
- Keeps legal, OSI, compatibility and enforceability judgments unresolved pending review.

`Project-KISS-v4-KOL-v1.0-proposed.patch` passed `git apply --check` and actual application to isolated temporary copies of both v4 sources. The resulting chapter and ADR text were checked. Both originals were retained unchanged. The detailed results are in `patch-verification.json`.

This is **not a patch for current GitHub main**: no v4 file exists in the inspected Project-KISS main tree or its four-commit main history. Importing or publishing v4 would be a separate action and is not authorized by this proposal.

## Repository observations

All seven repository metadata responses reported `license: null`. That field is a discovery result, not proof that the material has no copyright, is public-domain, is exclusively owned by the repository owner, or can be relicensed.

| Repository | Observed state | Rights-aware consequence |
| --- | --- | --- |
| [i-pp/Project-KISS](https://github.com/i-pp/Project-KISS) | Public; main `149f964fffd6fe9cd918dbc0ebb2f2c64666fa40`; five documentation blobs; complete recursive tree has no LICENSE/COPYING/COPYRIGHT/NOTICE file. | Documentation rights and permissions still require confirmation. Do not set a blanket KOL default. |
| [i-pp/AceIS](https://github.com/i-pp/AceIS) | Public; size 0; Git tree request returned 409, Git Repository is empty. | No tracked source or notice to migrate. Do not invent content or claim a migration completed. |
| [i-pp/ace](https://github.com/i-pp/ace) | Public; size 0; same empty-repository result. | Same. |
| [i-pp/paul](https://github.com/i-pp/paul) | Public; size 0; same empty-repository result. | Same. |
| [i-pp/gene](https://github.com/i-pp/gene) | Public; size 0; same empty-repository result. | Same. |
| [i-pp/peter](https://github.com/i-pp/peter) | Public; size 0; same empty-repository result. | Same. |
| [i-pp/project-kiss-infra](https://github.com/i-pp/project-kiss-infra) | Private; main resolved revision `e7bd7ec22f1855b027dd713118b54b394d7366a5`; 165 blobs; complete recursive tree has no LICENSE/COPYING/COPYRIGHT/NOTICE path. Actual implementation code and upstream runtime/model references exist. | Hold existing implementation outside KOL application until provenance, ownership, contributor permissions and dependency obligations are reviewed. Keep private content private. |

The complete recursive trees establish file-path inventory only. This was not an exhaustive legal or all-file header audit. No claim is made that all files lack inline notices or that all third-party dependencies have been discovered. No commit author's name was treated as a legal ownership finding.

Project-KISS's [current README](https://github.com/i-pp/Project-KISS/blob/149f964fffd6fe9cd918dbc0ebb2f2c64666fa40/README.md) says the repository is documentation-only, its fifth-edition sources and translation are preserved unchanged, and AceGeneralPublicLicense is only a name under consideration. [English v5 chapter 12](https://github.com/i-pp/Project-KISS/blob/149f964fffd6fe9cd918dbc0ebb2f2c64666fa40/docs/Project-KISS_design_v5_draft.en.md#12-public-development-and-licensing-philosophy) repeats the concept-only limitation.

The [shared development policy](https://github.com/i-pp/Project-KISS/blob/149f964fffd6fe9cd918dbc0ebb2f2c64666fa40/docs/development-policy.md) applies to the six public repositories, requires English for new project documentation, preserves historical source meaning, and requires dependencies and exclusions to remain identifiable. It explicitly says empty repositories do not need placeholder implementations or duplicate policy documents.

## Known third-party and uncertain-rights boundaries

These are concrete existing warning signals, not independent clearance conclusions:

1. The private infra [NPU distribution document](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/inference/aceis_npu_service/DISTRIBUTION.md#license-findings-and-release-gate) records an inconsistency: retained wheel metadata says MIT, while actual LICENSE.txt files refer to the AMD EULA and Ryzen AI notices. The notice filename is 1.7.1 while retained wheels are 1.8.0. The document also reports no separate quicktest model redistribution grant found in its bounded inspection. Do not treat the MIT metadata or upstream ONNX Runtime MIT license as covering the AMD runtime graph, compiler, XRT plugin, firmware or model. Exact applicable grants and notice/source obligations remain open.
2. Infra model manifests identify Qwen2.5-Coder, Qwen3-Coder GGUF and gpt-oss GGUF revisions and Apache-2.0 labels. They are discovery records, not a review of the complete artifact and upstream license chain. Preserve original licenses and notices; review model, tokenizer, quantizer, runtime and image separately. Sources: [Qwen2.5 lock](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/inference/vllm-b1/versions.lock.json), [Qwen3 record](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/evaluation/coder/model.json), [gpt-oss lock](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/inference/gpt-oss-b2/versions.lock.json).
3. The private infra [distribution notes](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/inference/aceis_service/distribution-notes.md) require separate review of Strata, tokenizer, model packs/GGUF, Ollama images/manifests, NPU SDK/firmware and explicit publication approval. They state LAF is a separate future distribution, not publication of AceIS. KOL must not collapse these product or rights boundaries.

## Proposed application plan

### Stage 0 Preserve and inventory

Freeze the exact proposed license text and source snapshots by SHA-256. Record every candidate repository, commit and path. Maintain an index with split component records rather than one unbounded file. Do not edit notices or add license identifiers in this stage.

Classify each candidate scope as:

- First-party, rights and application permission verified.
- Third-party, original terms and required notices retained.
- Mixed, generated or derived, requiring component-level analysis.
- Unknown, held outside the proposed application and distributable set.

No file enters the first category merely because it is in an i-pp repository, has an i-pp author, was generated by AI, or passed an automated scan.

### Stage 1 Confirm rights and isolate unknowns

For each scope retain origin and revision, actual applicable license text/hash, existing copyright/NOTICE/header text, author/contributor evidence, employment or contribution permission if relevant, derivative/generated inputs, intended modifications and distribution, and reviewer/date. Do not collect unnecessary personal information or publish private permission documents.

For unknown scopes record a private hold/quarantine entry with original path/hash, reason, responsible person and clearance condition. Exclude it from application, build/release packaging and automatic rewrites. Preserve the original location and bytes until an authorized, reversible isolation change is separately approved. A hold record is not a license, permission or proof that publication is allowed.

Exit a hold only with adequate rightsholder evidence, an applicable permission, or a legally reviewed replacement, plus Owner approval for the intended use. A legal right to use material under its original license does not automatically give permission to relicense it under KOL.

### Stage 2 Review the proposal

Review technical operability, evidence integrity and editorial clarity separately from legal review. Confirm the exact formal name, complete text, version and provisional identifier. Resolve required source disclosure, network use, derivative/combined-work treatment, patents, trademarks, warranty, liability, termination/cure and applicable law in the actual license proposal, not by implication in this migration plan.

Keep KOL compatibility, OSI approval and enforceability claims unapproved unless independently supported. Confirm whether documentation, test fixtures, models and generated assets need different terms. Do not assume all materials should use one license.

### Stage 3 Obtain three scoped Owner decisions

1. Formal adoption: exact KOL text/hash, version, canonical location and maintenance authority.
2. Publication: destination, visibility, files and revision; confirm no private evidence or unapproved upstream payload is included.
3. Existing-code application: repository/commit/path allowlist, rights evidence, notice preservation, exclusions and release consequences.

The same Owner decision may explicitly cover multiple gates, but none is inferred from drafting, review, CI success or the old public-development aspiration. Necessary rightsholder permissions remain independent prerequisites.

### Stage 4 Prepare an exact application diff after approval

Prepare a bounded draft PR or local patch only within the later approved scope. Add the approved custom license text and mapping, preserve all old notices, keep third-party terms distinct, and identify held paths explicitly. Do not rewrite Git history or retroactively claim previous releases were KOL. New first-party work may use KOL only after its actual owner/permission and adoption are established.

For current Project-KISS main, propose a new English licensing update and a README pointer, rather than silently altering preserved v5 source/translation. The v4 patch remains a review artifact unless importing or editing a particular v4 copy is explicitly approved. Empty implementation repositories need no placeholder migration.

### Stage 5 Validate and separately release

Check that every selected path has a deliberate disposition, no source or notice was silently skipped, the approved text/hash matches the custom identifier, copyright/NOTICE preservation is verified, and unknown or incompatible material is excluded. Compare a before/after notice inventory, inspect packaging and dependency graph, and retain the exact approvals and review results. Include adversarial tests for real GNU AGPL IDs, third-party exceptions, mixed works, ambiguous package metadata and unknown ownership.

CI should report missing mappings, unexpected files or changed notices and fail closed. It must not rewrite a license identifier to make a check pass. Publish/apply only through the separately authorized action and verify the exact result. An unapplied, tested patch is not an adopted or legally cleared license.

## Verification and limitations

- Read-only GitHub metadata, recursive tree, four main commits, branches, targeted documents and connected Space files were inspected.
- The v4 license chapter and ADR text were compared across both native copies.
- The proposed patch was checked and applied only to disposable local copies, then compared with the intended text.
- Existing repository and Space originals were not changed. No branch, PR, comment, commit, registry artifact, permission or external publication was created.
- Legal validity, copyright ownership, contributor authority, patent clearance, entire dependency closure, runtime redistribution rights and compatibility were not established. These remain adoption/application blockers, not reasons to stop preparing a draft.

Canonical operating references: [orchestration architecture](https://github.com/i-pp/ai-orchestration/blob/394bf5377c2b82bb6f660ca917192bdbe337bc85/docs/ai/orchestration.md) and [execution policies](https://github.com/i-pp/ai-orchestration/blob/394bf5377c2b82bb6f660ca917192bdbe337bc85/docs/ai/policies.md). They distinguish reversible preparation from publication and other high-impact actions.
