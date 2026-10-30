Strata retry02 preparation — not authorized or executed

The owner must separately approve STRATA_RETRY02_AFTER_ACCIDENTAL_INTERRUPT. approval-PENDING.json deliberately has approved=false and blank owner reference/time. No approval, intent, service, container or model operation was registered by this preparation.

Files for the parent integrator:

- retry02_strata_host.py: fixed human-host entry point. No flag prints PREPARED with generation_requests=0. The execution flag is --retry-human-approved; task/staging layout is rejected for execution.
- host_strata_trial.patch: small base-class hooks before_unload/build_packs plus PACK_HOOK_VERSION=1. The complete modified base copy is provided solely for review/fake tests. Applying this patch and copying the new retry module is the parent's responsibility; no live repository was edited here.
- approval-PENDING.json: exact one-attempt/one-generation/2400-second proposal, new approval reference required; both prior approval references are refused.
- test_retry02.py: thirteen CPU fake regressions. Prior seventy-eight CPU tests also pass with the modified base class (91 total).

Fixed prior run: strata-20261030T072213Z-3b931781. Summary SHA256 94a89fedbe92d5cca1d614fa02413b6d70508909fe0f9e5e5cff5cab502d6bbc; must show full_build interrupted, generation0, source metadata unchanged, and confirmed 30B RESTORED with other fixed router models unloaded. UNKNOWN or unconfirmed recovery is rejected.

The parent's pilot identity must be installed as owner-only <PROJECT_ROOT>/agents/local_llm/.runtime/strata-retry02-pilot-identity-20261030.json, SHA256 36cf730d13c9f13eeba6f3b4f84b5284762c40b3bd832573f7739e3120a6b8b6. Its schema binds all five files, prior summary, prior pilot_verify receipt, and full_reusable=false. The retry approval is a separate owner-only .runtime/strata-retry02-approval-20261030.json. Keep the original prior run and partial full unchanged.

Order: new approval and fixed prior/artifact verification; existing coordinator human-host guard; common generation lock and fresh same-endpoint idle checks; unique O_EXCL intent, file+directory fsync; original Trial lock/idle/resource checks; imports; while 30B remains loaded, full pilot file SHA/inventory/stability and old semantic-verifier receipt check, pack geometry check, then exactly one existing strata_pack.py verify against the old pilot. Verification reads the old pack; stdout/stderr/result files are stored in the new run. Only after these checks is 30B unloaded. Build and verify a fresh new-run/full with48layers, then retain the existing index/tokenizer/one raw GEN/owned cleanup/30B restoration flow. No pilot rebuild and no old-full reuse.

Fixed source verify/verify_experts were inspected as text: they read the manifest/source/pack through read-only open_shard, compare decoded values and print results. They do not write old pack files. No acquired source code was imported or executed during this preparation.

Capacity monitoring is explicitly soft sampled, without a namespace/cgroup/hard-cap change:

- Cumulative logical data <=120GiB across the fixed prior run, <PROJECT_ROOT>/.cache/backend-evaluation/strata-v027-e0152 (software/venv/source/archive tree), and the new run. Existing old partial data count at full current size; this is not a resettable growth baseline. Roots may not overlap. Symlink targets are not followed or counted.
- Free disk >=100GiB at the start/pre-unload gate; continuation stops below32GiB. Equality32GiB is allowed.
- Existing new-run70GiB logical-byte limit remains. The cumulative and free-space sample is attached to the existing owned-process0.5-second polling. Overshoot between samples and filesystem accounting differences remain possible.
- Existing start RAM24GiB, runtime RAM16GiB floor, GPU58GiB, native process RSS32GiB soft limit, swap-growth0, finite stage deadlines, total2400seconds/recovery reserve and one-GEN limits remain unchanged. Pilot hashing checks stage safety/deadline approximately every0.5seconds.

The exact same coordinator/endpoint/common-lock and UNKNOWN-no-resend semantics are retained. Surviving/unreadable owned processes prevent30B restoration. A failed or interrupted CPU stage with confirmed cleanup may restore30B; uncertain cleanup or lifecycle operations remain UNKNOWN with no automatic replay. The unique retry02 intent remains consumed even if a later check fails. This is a regular CLI workflow guard, not an OS boundary against a malicious owner rewriting trusted code/records.

Validation: thirteen new CPU fake tests cover prior UNKNOWN/recovery rejection, changed approval/limits/identity, pilot tampering/extra files/symlinks, no unload on preflight failure, read-only pilot reuse before unload, fresh-full-only output and preserved old bytes, unsafe cleanup blocking restoration, existing UNKNOWN marker,120GiB cumulative accounting,32GiB free floor,70GiB per-run retention, no-flag PREPARED, missing hook refusal and one consumed intent. With existing tests:91PASS. No actual socket, engine, acquired-source, GPU, Docker, download or service operation occurred.

The retry02 entry point starts its2400-second trial clock at main() entry, before approval/artifact verification and coordinator checks. ReplayTrial receives that monotonic timestamp; stage safety/remaining includes all of that elapsed time. Existing asset-verification file IO itself has no new hard timeout and occurs before30B unload. If preflight exhausts the remaining budget, safety rejects before pilot verification/unload; no late model operation is attempted. The reserve remains165seconds as in the reviewed base. A fake2236-second preflight delay verifies no stage process, pilot verification, unload or generation occurs.
