# acc output licensing policy candidate

**Status: unadopted private review candidate.** This policy interprets draft section 5 and makes no rights guarantee. No compiler implementation or artifact contents were validated by this drafting task.

## Core rule

We do not require AceIS, I-plusplus, or contributor credit merely because acc compiles, processes, transforms, or generates an output. Tool use alone does not make the output KOL. A user's own code is not relicensed by compiling it with acc.

The result can nevertheless contain material with its own terms. The candidate does not create a runtime-library or template exception. Before telling a user an artifact is free of attribution or redistribution conditions, inspect the actual linked, copied, generated, and packaged contents and the licenses of the user's inputs. This policy neither assigns ownership of output nor promises that generated or translated content is non-infringing.

## Cases to distinguish

| Case | Candidate KOL effect | Required review |
| --- | --- | --- |
| User code compiled with acc, without copied covered or third-party material | No KOL output attribution solely from tool use | Verify the premise and the input rights |
| Output includes covered startup objects, compiler helpers, static runtime code, or template text | Included covered portions retain KOL conditions; distributing AceIS Material needs its notice | Inventory exact portions and required delivery notices |
| Output depends on a separately delivered dynamic runtime | Tool use alone does not relicense the user's code; the runtime distribution has its own obligations | Review actual linking, packaging, runtime terms, and other applicable licenses |
| Output includes third-party libraries, assets, SDK files, or copied examples | Original terms remain | Review exact versions, linkage, notices, any source obligations, and restrictions |
| Output transforms another author's input | No automatic ownership or permission is created | Verify the input license and permitted transformation and distribution |
| Output only resembles a work or has unknown provenance | No clearance can be inferred from the tool or a scanner pass | Escalate uncertainty and review evidence before release |

Do not describe every output as “KOL licensed” or every output as “license free.” A compiler flag or metadata header is not enough to establish the bytes in a release.

## Runtime and generation inventory

Maintain a reviewed record for each runtime, startup object, helper implementation, standard-library component, built-in source fragment, template, sample, and generated support file that can enter output. Include its repository path and immutable source revision, rightsholder, license text and expression, build and linkage mode, mechanism of inclusion, shipped artifact paths, notices, any exception, and approval evidence. Record “not present” only when checked; unknown is not absent.

Automated tests should distinguish pure user output from outputs that contain covered or third-party portions. The build should make the included components observable through a link map, manifest, dependency report, or another justified method. A string search alone cannot establish absence of copied code.

## Unresolved decision about no-credit runtime output

The user's direction clearly removes credit based solely on using acc. If the intended policy also exempts copied AceIS runtime or template material from attribution in downstream outputs, an explicit additional license exception is needed. Do not infer that exception from the tool-use rule. Owner and counsel must approve its precise materials, covered rights, conditions, interaction with contributor permissions, and version. Third-party obligations cannot be waived by AceIS.

No runtime exception is included in this candidate. No custom SPDX exception identifier is invented. If an exception is later approved but is not on the SPDX exception list, represent the whole approved combined text through an appropriate LicenseRef rather than fabricating a registered `WITH` exception. See [SPDX expression rules](https://spdx.github.io/spdx-spec/v2.3.1/SPDX-license-expressions/).
