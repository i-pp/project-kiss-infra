# Lightweight client acceptance, 2026-11-07

## Result

The independent client used the guarded local Router to request actual model
repairs, apply accepted canonical candidates in new private directories, and run
tests. Three small public pure-function tasks all passed their supplied cases
(3/3 in this deliberately small sample, not a general task-completion benchmark).
Original inputs were never overwritten. No paid/cloud model API was used.

- Clamped sum, GPT-OSS120B: baseline1/4, candidate4/4, one attempt,6.68s workflow.
- Median of three, GPT-OSS120B: baseline0/4, candidate4/4, one attempt,5.87s.
- Safe division, Coder Next: baseline3/4 with ZeroDivisionError, candidate4/4,
  one attempt,15.36s including the Router's large-model switch/load.

Each workflow time includes model request/polling, validation, candidate write and
after-tests; it is not a pure decode latency. Median ran08:56:08.494–14.377 UTC;
safe division08:56:14.377–29.749 UTC. The clamped-sum run preceded them in the same
session. The client used a maximum of768 output tokens per repair request.

The source/cases are committed under `examples/`. The correct candidate expression
is not part of the validator. The same grammar accepts wrong arithmetic, which
fails actual cases. A model could pass these visible cases with a poor general
solution; hidden-case/real-project evaluation is still required.

## Regression and independent review

The final local host run passed45 tests:26 existing GPU service tests and19 new
CLI/repair tests. Coverage includes single submission/no replay after transport
uncertainty, job identity/ID retention, cancellation DELETE once, owner-only Unix
socket, immutable signatures, rejected imports/attributes/private identifiers,
builtin shadowing, nested functions/defaults/decorators, encoding-cookie
canonicalization, declarative case validation, no existing-directory overwrite,
and memory-limit failure. A mocked model returning a wrong candidate then a
correct one proves test-diagnosis feedback and a second iteration; the hardware
runs happened to succeed on the first attempt, so a real-model second iteration
is not claimed.

An independent read-only review found and verified fixes for encoding-cookie
source confusion, lost job IDs, and nested-function grammar bypass. Its pure/mock
checks and original attack fixtures passed after correction. It did not execute
the hardware service or model and is separate from the operator's45-test/hardware
results. No unaddressed pre-execution blocker remained in that review.

The default isolated command context cannot bind the test socket (EPERM). The
host-local acceptance used the selected desktop's authorized host command context,
without disabling any OS/network setting. The bounded repair runner itself always
uses Python isolated mode plus its child-only resource limits; there is no
unsandboxed retry of arbitrary model-proposed code.

## Running state and preserved work

After regression and before the model runs, GPU health was ready, Flash resident,
NPU ready and the queue empty. The existing GPU/NPU services, AceIS HTTP/Tunnel,
events worker, desktop notifications and orchestrator daemon were all active.
The final model runs used the same guarded service; no daemon, MCP, Tunnel, auth,
SSH, firewall or unrelated container setting was changed. No new TCP port,
credential, host package, driver or BIOS change was introduced. No service restart
was needed for this client-only work. The original GPU PR and local-only MCP
candidate are retained separately.

## Scope and remaining acceptance

One EVO-X3 represented logical PC-A (model service) and PC-B (client/tests).
Two physical PCs, WSL, LAN transport/authentication, multi-user quotas, durable jobs,
full-context/long-soak behavior and a general repository/shell agent remain
unverified. The client currently repairs only bounded pure Python functions with
declarative cases. It is not a Codex model-provider end-to-end acceptance.

GPU generation and NPU health are integrated at the existing server boundary;
classification remains the independent NPU service's own contract. NPU execution
is not inferred from these Python repair tests. See the separately accepted NPU
work for hardware/mixed-provider evidence and fault recovery.

Docker redistribution is a later, independent platform deliverable. No image was
published. The host supervisor currently controls Docker, so it must not simply be
shipped with a host Docker socket. Strata/model/tokenizer/Ollama/NPU SDK/firmware
licenses, reproducible builds, device permissions, clean-host installation and
redistribution rights still need explicit checks. A generic platform release is
not publication of AceIS itself. See `../aceis_service/distribution-notes.md`.

Implementation-assistant launch selection: `gpt-6.1-sol`; actual runtime model
metadata could not be independently verified. Hardware inference models were
explicitly selected as GPT-OSS120B and Coder Next through the Router. No GPT-6 Luna
was selected for this task. Product naming is provisional; existing identifiers
were not mechanically renamed.
