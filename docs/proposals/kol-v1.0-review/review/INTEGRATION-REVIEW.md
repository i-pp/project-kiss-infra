# Integrated private draft review

## Scope checked

The repository target is the existing private `i-pp/project-kiss-infra`, with base commit `e7bd7ec22f1855b027dd713118b54b394d7366a5` and tree `dc7662a122c8783ca5763b7da4e1d645b2063406`. The new `docs/proposals/kol-v1.0-review/` subtree does not exist in that base. No existing file is replaced, moved or deleted. The public Project-KISS and empty AceIS component repositories are excluded from delivery.

The source component manifests were verified before assembly. The complete seven requested texts and Apache comparison are copied without content changes. Original v4 sources remain unchanged and are not imported. The audit's commit-specific private findings stay in the private review repository. CI source, tests, fixtures, policy and baseline are copied without functional changes. The verbose test log is omitted under the repository's no-logs policy; the verification JSON and accompanying prose identify this omission, and the copied CI manifest is regenerated for the delivered files.

The review wrapper distinguishes legal drafting, repository rights clearance and mechanical tests. Its commands run the entire fixture suite and artifact check from the delivered layout. The disabled workflow is not an active CI integration, and the synthetic fixture license does not install or adopt the legal candidate.

## Existing reviews

The [drafting review](../license/review/DRAFTING-REVIEW.md) records independent legal-scope consistency and English-Japanese parity checks. It is not qualified legal advice. The [CI review](../ci-prototype/docs/CI-REVIEW.md) records independent technical review, reproduced gaps, regression fixes and a final independent 74-test pass for the isolated checker.

## Required later review

General breach, cure and downstream rights, patent reach and retaliation, exact rights holders and contributor authority, real runtime/template treatment, compatibility, jurisdiction and license stewardship remain Owner and legal decisions. Real build provenance, dependency closure and externally trusted CI enforcement remain technical integration work. Passing synthetic tests cannot resolve those questions.

No review here grants approval to merge, adopt, relicense, activate workflows or publish. Exact local check results are recorded in `INTEGRATION-VERIFICATION.json`. A separate final independent integration review, if completed, is recorded in `INDEPENDENT-INTEGRATION-REVIEW.md`.

## Operating sources

- [Orchestration architecture](https://github.com/i-pp/ai-orchestration/blob/main/docs/ai/orchestration.md), observed blob `b27d0e66daefea0498165c5a23c057ebeafe7bd9`.
- [Execution policies](https://github.com/i-pp/ai-orchestration/blob/main/docs/ai/policies.md), observed blob `0554d18499161015185e7f6fe821fd0ce4a5175d`.
- [Target repository instructions](https://github.com/i-pp/project-kiss-infra/blob/e7bd7ec22f1855b027dd713118b54b394d7366a5/AGENTS.md), blob `b9b06434a68455f946e4d9d1cbbd72e615c6fead`.
