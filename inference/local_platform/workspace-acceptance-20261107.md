# Selected-project client acceptance, 2026-11-07

## What passed

The client now restores a controlled regression in an existing project module,
not just a known pure-function AST. It reads selected files, applies a hash-guarded
edit in a fresh private snapshot and automatically runs unchanged tests inside
the accepted container boundary. Original checkouts are never written back.

On the final fixed v4 client, GPT-OSS120B and Coder Next each made the same intended
one-line repair in two model turns; all12 selected tests passed. The candidate
files are byte-identical to the clean CLI at base829a44c. An independent read-only
review confirmed both patches, all five read-only inputs and all six repository
originals unchanged. It did not execute the models, tests or containers itself.

This is one controlled repository-regression task, not an unknown production bug,
a broad project-agent benchmark or a general model ranking. The final client
still requires independent diff review and performs no original-source commit,
merge or writeback.

## Fixed source and task

Base: private project-kiss-infra revision
`829a44cb949578d9111c2ecb31ea36aa4b3f88d5` (GPU/NPU Draft PR #9).
The six-file operator manifest is `examples/cli-regression-task.json`.
A private copy of `inference/local_platform/cli.py` deliberately replaced only
ClientCancelled's received job identifier with None. The selected original
`test_cli.py` and its four other input dependencies were copied unchanged.

Baseline:12tests, one failure in test_cancel_preserves_id_and_calls_delete_once.
After the model's edit:12tests, no failures/errors/skips. The changed CLI hash is
`b0ea01265e77f12b9883777e89c40deaeb371b612e6aad8af31a84e1d4d59d52`, matching
the clean tracked source. The permission validator contains no expected solution.

To reproduce, start from that fixed Git revision, prepare only a NEW private
source copy of the manifest's six files, apply the single described regression
there, and use the manifest with the command in `workspace-client.md`. Never inject
the regression into the original checkout. This requires the already configured
local inference service and audited cached test image; it is not a clean-host
installation or portable-container claim.

## Regression and independent review

Final trusted unit/mocked suite:173 tests (66 previously accepted GPU/NPU/client
checks plus107 new workspace/controller/runner checks). These are separate from
real model and real container acceptance below.

Review found and verified fixes for duplicate/fenced JSON, stale test evidence,
path-versus-retained-fd root replacement, unexpected snapshot entries, Ctrl-C and
second-interrupt cleanup reporting, manifest/runner selection disagreement and
combined integrity loss with unconfirmed test stop. The client preserves the
actual latest runner result and uncertainty instead of silently continuing or
reusing earlier baseline evidence. The final frozen runtime review found no
remaining static blocker in the stated private trusted-host scope.

The model cannot supply shell/image/permission options. Selected tests stay
read-only. The controller checks directory identity and exact entry sets, uses
single-link files, guards edits with current full-file hashes and verifies actual
mounted hashes before project imports and after tests. The candidate must have
nonzero, nondecreased test count, matching tested content and confirmed cleanup.
Docker is not represented as a cheating-proof grader or a hostile-kernel sandbox.

## Real containment: seven operator probes

All seven expected boundary outcomes were accepted on EVO-X3 using only the
already-installed audited image
`sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c`.
Its recognized repository Dockerfile pins Ubuntu26.04 and installs compiler/Python
packages; its existing launchers already identify this exact image. No pull,
image build, package installation or host permission/security change occurred.

1. Six in-container tests passed: non-root caller UID/GID; zero effective
   capabilities and no-new-privileges; read-only writable-source mount; no Docker
   socket/GPU/NPU devices; loopback-only separate network namespace;512MiB memory,
   no extra swap,64PIDs, core0 and nofile128 limits.
2. A30s sleeper hit the3s host deadline, failed rather than passed and was removed
   with stop confirmed (3.09s observed).
3. Oversized stdout hit the64KiB transport cap and failed with confirmed removal.
4. Cancellation after confirming the container was running returned cancelled
   with confirmed removal (0.62s observed).
5. Changing an approved file between create and start was rejected by the mounted
   pre-import hash guard; project-import marker never executed.
6. Replacing the snapshot root between create and start was rejected before
   project import by the device/inode check; cleanup was confirmed.
7. The attached Docker client was terminated after0.5s while its container stayed
   running. A trusted PID1 watchdog then exited124 on its own3s bound, closing the
   namespace including a setsid descendant. Three namespace processes were
   observed before termination; stop followed about2.56s after detach, then exact
   removal was confirmed.

Negative probes intentionally produce failed/cancelled runtime statuses. They
are passing safety checks, not successful programming tasks. Every test container
was owned, identity-checked and removed. No preexisting container was stopped.

## All local-model task runs, including failures

Three development runs used GPT-OSS120B before the final v4 control was fixed:

- v1:21.79s/eight model turns, seven empty final contents and one flattened JSON
  object; all were rejected, no edit, final test still failed.
- v2:23.96s/eight turns, nested records but overlarge read hints rejected; no edit,
  final test still failed.
- v3:58.46s/eight turns, the correct one-line edit occurred, but the model did not
  request tests and repeated stale-hash edits. No final tests, so the run failed.

These were started failed runs, never relabeled blocked or silently omitted.
They motivated explicit plain-text nested records, read hints clipped to the
unchanged60-line/2KiB budget and mandatory client-run tests after each accepted
edit. They are not controlled comparisons of model coding quality.

With the exact same final v4 controller/source/manifest/image/test selection,
8192 server context, output cap768 per request, maximum8 turns and300s task bound:

- GPT-OSS120B warm: completed,2 turns,13.85s workflow,12/12tests.
- Coder Next after guarded120B unload/load: completed,2 turns,20.01s,12/12tests;
  Ollama reported11.05s load in the first request, excluding other switch work.
- Coder Next warm repeat with no new switch: completed,2 turns,5.30s,12/12tests.

Both warm cases had sub-millisecond reported model-load durations per request.
The configured models use their existing different GPU-layer/reasoning settings
and produced different token counts; workflow time is not same-token throughput.
This single simple task shows equal accepted code and a faster warm Next workflow
under these settings, not a general coding-performance conclusion. Accuracy takes
priority over speed. Neither model authored the fixed tests, so this does not
evaluate the user's most important criterion: creating correct tests from a
specification. The separate [evaluation design](test-quality-evaluation.md) covers
independent expected values, normal/boundary/error coverage and mutation detection.

Counting:one unique planned task, exercised on two models, with an extra warm
Next repeat. All three final-v4 executions completed; the three earlier executions
failed. No model-task execution was blocked or unexecuted. Do not call six runs
six distinct tasks or combine changing controller revisions into a model ranking.
A separate one-response protocol diagnostic was not a programming task.

## Final running state and limits

Final observed state: GPU/NPU ready, Flash resident, Coder Next selected, empty
queue/no fault. All seven protected/owned services were active and no new test
containers remained. No inference/NPU/MCP/daemon/notification/Tunnel restart or
configuration change was needed for this client work. Existing PR #1/#8/#9 and
local-only MCP work remain protected. No auth/network change, credential, external
listener/publication, model/cache/log upload or merge occurred.

The authoritative distributed Plan was separately updated in its original local
agent-orchestrator path only, preserving its unrelated dirty work, HEAD/remotes
and190 other files. It treats Codex/Claude/OpenCode as optional, keeps P0 independent
API/GPU-NPU/client/task completion, and makes practical NPU interpretation→GPU
assignment→evaluation→next action a future milestone. A suitable NPU model is
unconfirmed; explicit CPU/GPU fallback remains possible and this does not block P0.
The SDK classifier's plumbing result is not that future milestone.

Still unverified: multiple unrelated real bugs/held-out tests, broader project
build systems/new-file workflows, multi-user/multi-client fairness and durable
resume, second physical PC/WSL/authenticated transport, long soak/full context/
reboot and clean-host licensing/distribution. Native compiler/build/load/ABI/SIMD
fixtures need a separate reviewed execution profile; these Python checks do not
accept them. No compiler body was implemented or executed here.

Assistant launch selections were gpt-6.1-sol; actual assistant runtime metadata
could not be independently inspected. Local runtime tasks explicitly used
GPT-OSS120B and Coder Next through the existing guarded Router, with no paid/cloud
model API fallback. No GPT-6 Luna was selected for this implementation work.
