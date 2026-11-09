# Decisions required before adoption

**Current state: no adoption, publication, relicensing, signing, or rights grant has been executed.** The candidate is a legal drafting aid. Qualified counsel should evaluate legal meaning and enforceability for the intended jurisdictions. Owner must approve the exact decisions and scope; the following questions do not authorize an action by themselves.

## Blocking decisions

1. **Identity and rights.** Confirm the legal rightsholder and license steward, whether “I-plusplus Inc.” is the correct legal name for relevant copyright, and the authority of the person approving. Attribution to I-plusplus is not proof of ownership. Complete the rights ledger for each proposed file and existing contribution. Until then, the requested corporate header is only a conditional template.
2. **General breach and remedies.** Decide the effect of a notice or other non-patent breach: whether permission terminates or is suspended, whether cure is available, when reinstatement occurs, whether repeated or intentional breach differs, how downstream recipients are treated, and which obligations survive. The current text makes permission conditional and expressly defines patent termination only. It supplies no complete general cure mechanism. Do not mistake that unresolved point for a finished enforcement design.
3. **Compiler output boundary.** Confirm whether “no credit for acc output” means no credit solely from tool use, as drafted, or an exception for copied AceIS runtime/template material as well. An exception would need exact materials, contributor authority, conditions and separate approval; it cannot waive third-party rights. Test against actual startup objects, helper code, runtime libraries, templates and bundled assets.
4. **Patent reach.** Approve necessary-claim scope at submission, treatment of later acquired licensable patents, absence of an affiliate-control definition, cross-claim/counterclaim treatment, whether a defensive exception is intended, termination timing and any restoration route. Current patent termination has no restoration provision and does not by itself terminate copyright rights.
5. **Attribution mechanics.** Approve the AceIS Material definition and required credit, how components are identified, retention of individual notices, translations, and restriction to a supplied NOTICE or license document. Confirm that screen/manual credit is optional and that names are factual origin statements, not endorsement or a blanket trademark license.
6. **Additional liability.** Approve the deliberate absence of Apache section 9's express indemnify/defend requirement. Current text limits undertakings to the distributor's own behalf but does not shift claims through an express indemnity. Decide whether to retain that simpler choice.
7. **Jurisdiction and mandatory law.** Review warranty, title and non-infringement disclaimers, exclusions for direct loss and negligence, mandatory consumer and product-liability law, translation status, remedies, severability, and whether any governing-law or venue clause is needed. None is currently selected. No provision overrides rights that cannot lawfully be excluded.
8. **Contribution process.** Choose the explicit acknowledgement and any DCO or CLA process for future work. Do not apply a new intake policy to past material by assumption. Decide how separate inbound terms and employer/contractor permissions are verified.
9. **License text stewardship.** Confirm the right to publish and reuse this independently named text, the final instrument extraction, version policy, stable publication location, digest, and whether copying or adapting the license text itself needs an express permission. No authoritative KOL URL has been invented. Do not call the draft a registered SPDX license or claim OSI/FSF assessment.
10. **Material and publication scope.** Separately approve exact repositories, revisions, file paths, exclusions, release artifacts, destinations, and public/private review boundaries. Approving the text alone is not approving its use on existing code or its public release. Complete dependency and compatibility review for each actual combination.

## Decision record template

- Decision and gate: `<license adoption | material application | publication>`
- Owner and authority evidence: `<verified identity and reference>`
- Date and explicit approval evidence: `<record>`
- Exact English text SHA-256 and version: `<digest and KOL v1.0 candidate/release identity>`
- Approved repositories, revisions, paths and excluded material: `<scope>`
- Rights and contribution evidence: `<private evidence references>`
- Legal and technical review findings and disposition: `<record>`
- Japanese reference revision and parity review: `<record>`
- Actual release artifacts and digests, if relevant: `<record>`
- Publication destination and audience, if relevant: `<record>`
- Conditions or items still blocked: `<record>`

Do not fill these fields with inferred consent or a passing CI result. An Owner decision cannot grant a third party's rights without sufficient authority.
