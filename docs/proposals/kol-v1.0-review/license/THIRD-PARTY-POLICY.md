# Third party licensing policy candidate

**Status: unadopted private review candidate.** This policy does not approve any dependency or declare compatibility. It preserves original rights and requires review of the actual distribution.

## Keep original rights visible

Third-party code, documents, libraries, templates, fonts, images, model weights, datasets, SDKs, firmware, vendored tools, and generated support material retain their original licenses and notices. Public availability is not a license. A repository with no identifiable license must not be treated as permissively licensed.

Do not stamp KOL headers onto third-party material, remove upstream copyright, or describe a mixed product as wholly KOL. First-party modifications to third-party material need an accurate portion-level record and must respect the upstream terms. A project-level license file cannot override them.

## Inventory before integration

For each component, record name, version, source URL, immutable revision or content digest, repository and artifact paths, actual rightsholders and notice texts, license expression, complete license and exception texts, how it is used and linked, whether it is shipped or downloaded later, modifications, and release obligations. Distinguish evidence from an unresolved interpretation. Keep private rights evidence out of public notices.

Review source and binary dependencies, transitive dependencies, container base layers, plugins, statically copied helpers, code generators and their templates, and runtime downloads. A package manifest is an input to the inventory, not the entire inventory. An SBOM describes components; it does not itself grant rights or satisfy all license terms.

## Compatibility review

Do not maintain a universal whitelist asserting that MIT, BSD, Apache, GPL, LGPL, AGPL, proprietary terms, or other families are automatically compatible with KOL. Review the exact version, exceptions, permissions, distribution mode, linking and copying facts, and the combined obligations. Familiar license names are not sufficient.

KOL's proposed mandatory AceIS attribution placement, notice retention, patent termination, and treatment of downstream terms can interact with other licenses. A permissive design does not prove GPL or proprietary-license compatibility. Assess the actual scenario and obtain qualified legal review where uncertain. Do not label KOL “GPL-compatible,” “Apache-compatible,” “OSI-approved,” or “FSF-approved” without an independently supported determination. No such determination exists in this pack.

For copyleft components, review any source delivery, written offer, installation information, modification notice, relinking, network interaction, and downstream-rights requirements that actually apply. KOL's lack of a source-publication duty does not waive duties of another component. For proprietary SDKs or content licenses, review redistribution scope, field or platform restrictions, and whether credentials or access are required. Do not accept new legal commitments or seek upstream permissions without the applicable authorization.

## Distribution packaging

Supply each included component's required license, notices, attribution, and other required materials. Preserve upstream NOTICE contents when applicable, distinguish origin credits from added project notices, and include a license index mapping components to actual installed paths. A KOL NOTICE credit does not replace upstream obligations. A link to a moving upstream repository is not a substitute for materials that must accompany distribution.

Verify each actual source archive, binary package, installer, container, runtime bundle, and documented download flow. If an obligation cannot be satisfied, stop that proposed integration or release and present Owner with the exact component, version, action, reason, evidence, and available lawful options. Do not erase a finding or classify an unknown file as exempt merely to make CI pass.

## Update and removal

Re-review changed license text, versions, dependency graph, linkage, copied files, and distribution modes. Record replaced and removed components so stale notices can be removed only when they no longer apply. Preserve required notices and evidence for earlier distributed versions. A successful scanner run supplements review; it does not prove ownership, completeness, authenticity, or compatibility.
