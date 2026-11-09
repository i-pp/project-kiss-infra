# KOL v1 private review pack

This pack prepares an independently named KISS Open License Version 1.0, an English candidate and Japanese reference, the requested operations policies, and an Apache comparison. It is ready for Owner and legal review, not adoption. No repository has been relicensed and no text has been published by this work.

## Read first

- `LICENSE-KOL-v1.0`: complete English proposed instrument with explicit review boundaries.
- `KOL-v1-JA.md`: non-authoritative Japanese reference, matched to its section numbers.
- `review/OWNER-DECISIONS.md`: blocking legal and Owner decisions. The general breach/cure mechanism needs a decision. A broader exception for copied runtime material is an optional Owner choice, beyond the drafted no-credit rule based solely on tool use.
- `APACHE-2.0-COMPARISON.md`: clause comparison and material departures, without a compatibility guarantee.
- `KOL-POLICY.md`, `ACEIS-NOTICE.md`, `ACC-OUTPUT-POLICY.md`, `CONTRIBUTOR-POLICY.md`, `THIRD-PARTY-POLICY.md`: proposed operational policies.

The exact interim identifier is `LicenseRef-KOL-v1.0`. It is project-defined, not a registered SPDX License List identifier. This pack asserts no OSI or FSF assessment. The requested `2026 I-plusplus Inc.` source header is conditional on actual ownership, not applied to files.

## Review boundary

The English candidate contains a review-only banner and BEGIN/END markers. They make its status visible and are not part of the proposed instrument. There is no operative copy at `LICENSES/LicenseRef-KOL-v1.0.txt` in this pack: copying the proposal into that location requires the later adoption decision and a separately approved, exact extraction. Policies cannot add terms to the instrument.

Commercial and private use, binary-only redistribution, proprietary integration, origin credit at redistribution, no output credit solely from acc use, retained third-party rights, patent permission and retaliation, no trademark grant, and warranty/liability limitations are included. No mandatory output splash screen or source-publication duty is introduced by KOL.

No general breach/cure/reinstatement clause has been invented. No runtime/template attribution exception has been invented. No file ownership, patent clearance, universal license compatibility, legal enforceability, source-inventory completeness, or working compiler implementation is certified.

## Checks for this review pack

`review/pack-manifest.json` records the file names, hashes and drafting checks. Hashes identify reviewed bytes; they do not prove legal authority or authenticity. These commands are review aids, not a Quick Start for AceIS or acc:

```sh
python3 -m json.tool review/pack-manifest.json
sha256sum LICENSE-KOL-v1.0 KOL-v1-JA.md KOL-POLICY.md
```

Run from this pack's root. Independent legal-scope and editorial review records are separate from metadata or packaging tests. Read those records before treating a check result as meaningful.
