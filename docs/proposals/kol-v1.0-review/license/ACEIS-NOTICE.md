# AceIS attribution policy candidate

**Status: unadopted private review candidate.** Apply only after the corresponding English license and material scope receive explicit Owner approval. This policy explains the draft's section 4; it cannot add license conditions.

## What redistribution requires

When a distribution contains AceIS Material covered by KOL, supply the approved English license and the following origin credit in an accompanying `NOTICE` file or license document:

```text
This distribution includes AceIS, developed by I-plusplus and the AceIS
contributors.
```

A translation with the same attribution is permitted by the candidate. Keeping the English sentence avoids translation drift. Do not replace I-plusplus with a different corporate form merely because a source-header template names I-plusplus Inc.; confirm the legal identity separately.

Also retain all applicable existing copyright, patent, trademark, attribution, and license notices for included material. Retain existing notices naming individual contributors. The collective wording does not authorize removing them, but does not require creating a new exhaustive contributor list. Include required upstream notices even when they differ from this template.

The obligations apply to original and modified redistributions, including binary-only products and proprietary products that include AceIS material. Moving code, changing product names, or stripping a header does not remove its origin. A standalone link is insufficient: recipients must receive readable license and notice copies with the distribution.

For an Object distribution that cannot reasonably contain original inline notices, reproduce applicable notices in its supplied NOTICE or license document. For Source, retain notices in the relevant files or accompanying notice files as stated by the candidate. Omit a notice only when it applies solely to material not included in the distribution, and record why.

## What remains optional

An About screen, product screen, website acknowledgement, or manual acknowledgement is recommended where useful, but not required by KOL and cannot replace the required distributed notice. Do not add mandatory splash screens, advertisements, backlinks, badges, or acknowledgements in every generated application. Use no logos or wording that implies endorsement.

Using acc alone does not require an output credit. Output that embeds covered material requires the separate analysis in `ACC-OUTPUT-POLICY.md`.

## A distribution notice template

This template is not a ready-to-ship notice. Replace placeholders only after checking the actual included material. Remove instructional placeholders from a release, not existing legal notices.

```text
AceIS origin credit

This distribution includes AceIS, developed by I-plusplus and the AceIS
contributors.

License

The identified AceIS material is licensed under KISS Open License Version 1.0.
A complete copy is supplied in <actual path in this distribution>.

Retained notices for included material

<Insert applicable original notices verbatim, with their component scope.>

Third-party material

<Identify included components and the supplied paths to their original
licenses, copyright notices, and other required notices.>

Distribution changes

<Identify modified files for Source or modified components for Object-only
redistribution, or state that this distribution makes no such changes only
when verified.>
```

Do not state that every file in the product is KOL. Do not fabricate copyright years, rightsholders, original authorship, contributor completeness, third-party clearance, or a warranty. A NOTICE is not a place to add restrictions to the license.

## Artifact checks

For each delivered archive, package, image, or installer, verify the actual extracted contents include the complete license, credit, retained notices, and change record in readable locations. Record their paths, the source commit and artifact digest. If an installer fetches additional components, review the fetched payload too. A repository-only NOTICE check does not prove that installed recipients receive the notice.
