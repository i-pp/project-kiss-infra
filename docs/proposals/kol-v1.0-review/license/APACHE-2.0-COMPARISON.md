# KOL candidate and Apache 2 comparison

**Status: unadopted private review candidate.** This is a drafting comparison, not a compatibility opinion. KOL is an independent new text. Apache's recognition and legal assessments do not transfer to it.

Read the [official Apache-2.0 text](https://www.apache.org/licenses/LICENSE-2.0) alongside the exact KOL candidate. The Apache column below is a compact paraphrase; it does not replace the instrument. Section numbers refer to those two texts, not to a claim of equivalent wording or effects.

| Topic | Apache 2 baseline | KOL v1 candidate | Consequence or decision |
| --- | --- | --- | --- |
| Copyright grant | Section 2 grants broad copyright permissions, including sublicensing. | Section 2 expressly permits use and covers each Contributor's rights within its authority. | Verify the rights-holding principal and contribution chain; a grant cannot cure missing rights. |
| Closed and binary products | Sections 2 and 4 permit modified and Object distributions; no mandatory source publication. | Section 2 expressly permits private changes, binary-only distribution and proprietary integration. | KOL imposes no source-publication duty; other components still may. |
| License delivery | Section 4 requires a license copy. | Section 4(a) requires a readable copy in distributed materials. | Links alone are insufficient under the candidate. |
| Original notices | Section 4 retains applicable Source notices. | Section 4(b) also provides a notice-document route for Object form. | This is explicit additional packaging wording, not simply an unchanged Apache condition. |
| Change notices | Section 4 requires prominent notices in changed files. | Section 4(c) allows a file-identifying change record and an Object-only component record. | Avoid implying source disclosure, but verify the change record actually identifies the affected scope. |
| Attribution placement | Section 4 allows several locations for applicable NOTICE attribution. | Section 4(d)-(e) requires a supplied NOTICE or license document; mandatory AceIS origin credit applies even without an upstream NOTICE. | KOL intentionally narrows placement and adds named origin attribution. Screen and manual credits remain optional. |
| Compiler output | No dedicated compiler-output provision. | Section 5 explicitly removes obligations based solely on tool use and preserves rights in protected included material. | Inventory runtime, template and helper inclusion; no blanket output clearance or runtime exception. |
| Patent grant | Section 3 covers necessary contributor claims and a defined Work combination. | Section 3 limits claims to licensable rights and the Work combination at submission. | Legal review must test scope, timing, future acquired rights and output scenarios. No third-party patent clearance. |
| Patent retaliation | Section 3 ends Work-specific patent grants upon specified litigation. | Section 3 terminates patent permissions for the Work on filing, including cross-claims and counterclaims. | No general copyright termination follows solely from this paragraph; defensive filings are not exempted. |
| Contributions | Sections 1 and 5 define submissions broadly and establish default inbound terms. | Sections 1 and 6 require an intentional offer under KOL and identify the rights-holding principal. | New intake needs recorded acknowledgement; no retroactive relicensing through a policy update. |
| Trademark | Section 6 withholds trademark permission with a limited origin-use allowance. | Section 8 grants no trademark rights and preserves required truthful attribution and independent legal rights. | No endorsement or logo permission. Avoid equating the two formulations. |
| Warranty and liability | Sections 7 and 8 disclaim warranties and limit liability subject to law. | Sections 9 and 10 use independent wording and preserve non-excludable and expressly accepted liability. | Jurisdiction and mandatory-law review remain necessary. No enforceability guarantee. |
| Paid support liability | Section 9 includes indemnity and defense obligations for additional undertakings. | Section 10 permits only own-behalf undertakings and does not impose an express indemnify/defend obligation. | This is a material departure needing explicit Owner and counsel review. |
| General breach and cure | No general notice-and-cure mechanism is stated. | Conditional permission, but no general cure or downstream-survival mechanism is specified. | This is an unresolved drafting issue, not a unique omission relative to Apache. Do not claim the candidate fully defines termination. |
| Legal entity scope | Section 1 groups specified controlled entities. | Section 1 uses the exercising person or legal entity without an affiliate-control definition. | Consider patent retaliation and group-company scope; do not assume identical reach. |
| Compatibility and recognition | Apache's status concerns that exact standard license. | No compatibility, SPDX-list, OSI or FSF determination is asserted for KOL. | Assess each exact license combination independently; no transitive recognition. |

The [Apache reuse FAQ](https://www.apache.org/foundation/license-faq.html#mod-license) explains that substantive modification yields a different license and recommends obtaining one's own legal advice. The candidate is therefore not named or tagged as an Apache variant. No claim of Apache Software Foundation endorsement is made.

## Compatibility work still required

A combination review must identify exact component licenses and exceptions, copyright and patent permissions, copied and linked material, notice placement, available downstream terms, source or installation obligations, and the actual distribution or network-service model. A syntactically valid SPDX expression does not answer those questions. Do not infer KOL compatibility from Apache compatibility discussions, permissive intent, a scanner's label, or another project's approval.
