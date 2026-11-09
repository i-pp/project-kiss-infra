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
or an exact-path accompanying `.license` file. The rightsholder for Yuji-created
project files in this scope is I-plusplus Inc. A root LICENSE does not change
the terms of every file, dependency, linked project or future contribution.

This change identifies 164 existing project-authored files from revision
`e7bd7ec22f1855b027dd713118b54b394d7366a5`: 124 source/configuration files
carry short SPDX headers, and 29 Markdown documents plus 11 JSON metadata files
have accompanying notices. The original bytes of those documents and metadata
are preserved, including dated engineering evidence and model-license fields.

The generated file `dev/aarch64/smoke/rust/Cargo.lock` is unchanged.
It contains Cargo-generated package metadata, not vendored package source.
This change makes no new copyright assertion or licensing determination about
that generated metadata. The project-authored `Cargo.toml` is marked separately.

The license instrument is reproduced without an added header or altered clause.
NOTICE, this guide, and the accompanying file notices are project licensing
materials. Future files and outside contributions require accurate ownership
and applicable license notices before KOL is applied.

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
comment syntax. Keep interpreter shebangs first. For commentless formats or
byte-preserved evidence, keep the matching exact-path `.license` file alongside
the covered file. Do not add a different license to an upstream payload merely
because a wrapper or build script uses it.

This change adds licensing information only. It does not update an existing
deployment, publish this private repository, or establish legal enforceability,
patent clearance, compatibility or certification.
