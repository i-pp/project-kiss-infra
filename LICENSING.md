<!--
SPDX-FileCopyrightText: 2026 I-plusplus Inc.
SPDX-License-Identifier: LicenseRef-KOL-v1
-->

# Licensing

The complete KISS Open License Version 1.0 is in [LICENSE](LICENSE).
The custom identifier `LicenseRef-KOL-v1` maps to the identical text in
[LICENSES/LicenseRef-KOL-v1.txt](LICENSES/LicenseRef-KOL-v1.txt). It is not an
SPDX License List entry or an OSI approval.

## First-party scope

KOL applies only to first-party material expressly identified by an SPDX header
or by path in the strict JSON notices below. The rightsholder for Yuji-created
project files in this scope is I-plusplus Inc. A root LICENSE does not change
the terms of every file, dependency, linked project or future contribution.

The original rollout identified 164 project-authored files from revision
`e7bd7ec22f1855b027dd713118b54b394d7366a5`: 124 source/configuration files had
short SPDX headers, and 29 Markdown documents plus 11 JSON metadata files had
accompanying notices. The 29 Markdown notices now appear in the documents
themselves, preserving their original contents and the exact notice scope.
The 11 strict JSON files retain their original bytes, including model-license
fields; their notices are now recorded by exact path in this guide.

The generated file `dev/aarch64/smoke/rust/Cargo.lock` is unchanged.
It contains Cargo-generated package metadata, not vendored package source.
This change makes no new copyright assertion or licensing determination about
that generated metadata. The project-authored `Cargo.toml` is marked separately.

The license instrument is reproduced without an added header or altered clause.
NOTICE and this guide are project licensing materials. Future files and outside
contributions require accurate ownership
and applicable license notices before KOL is applied.

## Exact-path notices for strict JSON

The following existing notices moved from individual companion files without
changing the covered scope or the terms of KISS Open License Version 1.0
(`LicenseRef-KOL-v1`). These declarations apply only to the files listed here,
not to every JSON file or to the repository as a whole. For these JSON files,
this section fulfills the exact-path notice described in [NOTICE](NOTICE);
the notice now appears here instead of in an accompanying file.

| Repository-relative file | SPDX-FileCopyrightText | SPDX-License-Identifier |
| --- | --- | --- |
| `dev/aarch64/versions.lock.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `dev/x86_64/versions.lock.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `evaluation/coder/model.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `evaluation/coder/tasks.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/aceis_service/config.example.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/gpt-oss-b2/versions.lock.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/local_platform/examples/cases.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/local_platform/examples/cli-regression-task.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/local_platform/examples/median3-cases.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/local_platform/examples/safe_divide-cases.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |
| `inference/vllm-b1/versions.lock.json` | 2026 I-plusplus Inc. | `LicenseRef-KOL-v1` |

Scope: This notice applies only to the project-authored metadata or documentation in this exact file. External material it describes retains its separate terms. This scope applies individually to each row.
When an already-cleared JSON file is added or renamed, update this exact-path
list and the CI license policy together.

## Separate third-party material

No vendor SDK, runtime, firmware, model weights, tokenizer payload or base image
becomes KOL-licensed through these source notices. JSON fields describing an
external model's Apache-2.0 license describe that model, not the license of
this project's metadata wrapper.

In particular, preserve the existing [NPU redistribution assessment](inference/aceis_npu_service/DISTRIBUTION.md)
and [planned container distribution notes](inference/aceis_service/distribution-notes.md). Their unresolved AMD
SDK/EULA, runtime, model and redistribution questions remain open. This source
licensing change is not clearance to redistribute those external artifacts or
publish an image.

Keep genuine upstream copyright, attribution and license notices with any
material later included. An accompanying NOTICE does not replace the full
licenses, required notices, source offers or other obligations that may apply
to a separate dependency.

## Notices and later changes

Preserve [NOTICE](NOTICE) where it applies to included material, as required by
section 4(d). Identify distributed changes under section 4(c). Credit in an
About screen or manual is optional. Using a KOL-licensed tool does not alone
license its output or require credit; copied or embedded covered material
retains its applicable terms.

For a file that supports comments, retain the short SPDX pair in supported
comment syntax. Keep interpreter shebangs first. For the strict JSON files
listed above, retain the exact-path declaration in this guide without modifying
the JSON. Do not add a different license to an upstream payload merely because
a wrapper or build script uses it.

This change adds licensing information only. It does not update an existing
deployment, publish this private repository, or establish legal enforceability,
patent clearance, compatibility or certification.
