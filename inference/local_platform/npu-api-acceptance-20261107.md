# Unified private GPU/NPU API acceptance, 2026-11-07

## Result

The existing owner-only Router endpoint now provides capability discovery and
independent NPU classification. The product-independent CLI called that same
endpoint for one synthetic NPU request during an active Flash job. All three GPU
model routes completed after deployment. There is no new TCP listener, remote
authentication mechanism or cloud fallback.

Deployed code: `c1b5a2b3ad173680b506c0455afdeeab9a38ca97`, copied from Git to a
new private versioned source snapshot rather than running a mutable worktree.
The optional NPU service/worker/SDK/model were not changed. The only deployment
change was a new WorkingDirectory-only drop-in on the owned GPU service; its
original unit and all other services were retained.

## Tests and independent review

The final full host regression run passed66 tests:26 GPU service,18 NPU bridge/API
and22 client/repair. Private mock endpoints exercised classification's separate
slot, absent/busy/failed NPU, GPU readiness/request continuation, input/output and
provenance validation, body bounds and no retries. Existing GPU serialization,
cancellation, physical release, ownership and native-engine tests remained passing.

Independent read-only review found and verified fixes for request serialization
expanding past the upstream100000B limit and valid JSON being accepted inside a
truncated Content-Length frame. Inputs now match NPU float32 normalization, use
compact JSON and recheck transmitted size. Responses require exactly one valid,
bounded Content-Length, no Transfer-Encoding and a complete body. The NPU
implementer also checked contract alignment and identified the worker's legitimate
9-digit maximum-float32 decimal; output validation accepts that representation.

The reviewer separately passed30 focused tests and eight real HTTPResponse-parser
cases, including truncated/duplicate/missing/invalid length and empty
Transfer-Encoding. It re-read the API/README and did not operate hardware services
or models. No pre-deployment blocker remained. Hardware evidence below is separate.

## Idle-only deployment

Three consecutive checks showed ready, no fault, no active job and empty queue.
No prior drop-in existed. The fixed code snapshot was installed privately and a
new WorkingDirectory drop-in added; idle was checked again immediately before one
normal restart of only the owned GPU unit. Readiness returned in5.75s with changed
PID, Flash resident and independent NPU ready. No repeated restart or limit reset.

No existing AceIS daemon/MCP/HTTP/Tunnel/notifications or NPU unit was restarted.
No package, driver, BIOS, credential, privilege, network/security setting or model
asset was changed. No model/cache/raw evidence/vendor runtime was uploaded. No
image was published or PR merged. The code snapshot avoids worktree branch-switch
changes to live source. Do not edit it in place.

## One-endpoint hardware smoke

Flash ran09:14:37.323–42.021 UTC,128 tokens,4.70s. Classification began09:14:37.524
and returned09:14:37.755 while that GPU job was still running. This establishes
active-request overlap, not simultaneous GPU/NPU kernel timing. Client elapsed
230ms included Python startup/validation/transport; worker reported156.16ms after
long idle. This single sample is not a throughput or tail-latency benchmark.

Input:3072 values `float(i%251)/250`. The response identified RyzenAI/VitisAI,
execution_target npu, execution_scope mixed_npu_cpu, verification_kind
ort_warmup_profile and execution_verified true. Ten logits matched the separately
accepted synthetic probe, class0. The CLI explicitly set
application_accuracy_verified false. Warmup EP execution evidence is not
per-request hardware counters, pure-NPU work or accuracy validation.

Further GPU requests on the same guarded endpoint:

- Coder Next64 tokens:12.69s including load, completed.
- GPT-OSS120B64 tokens:19.95s including guarded switch/load, completed.

All three reached the configured output length. These are routing/runtime
regressions, not answer-quality or coding-task success evidence. The separate
three-task bounded repair result remains in `acceptance-20261107.md`.

Final health: ready/fault null, Flash resident,120B selected, no active job/queue,
NPU ready with mixed scope. Before/after samples showed available RAM52.51/36.88GiB,
final VRAM51.24GiB used and swap growth94.43MiB, below the512MiB guard. Zero swap
growth is not claimed. Final memory full PSI avg10=.13%. These are two samples,
not measured extrema. The watchdog ran throughout. Seven owned/protected units
were active after the smoke.

## Rollback and remaining acceptance

The only unit addition is `aceis-inference.service.d/20-independent-npu-api.conf`,
pointing WorkingDirectory at the fixed private snapshot. During a confirmed idle
window, save/move only that new drop-in to a non-`.conf` filename, daemon-reload,
and normally restart only `aceis-inference.service` to restore the retained old
WorkingDirectory. Verify readiness/physical release; never repeat starts after an
uncertain stop. Preserve the snapshot/evidence until rollback is accepted. The
NPU service remains independent.

Unverified: second physical PC/WSL/authenticated remote transport, multi-user
quotas, resource-optimized multi-client scheduling, long soak, full context,
physical reboot, clean-host container distribution/licensing and an application
NPU model with validated labels/preprocessing. No NPU outage was injected here;
this stage uses mock outage tests and retains the earlier separate hardware
fault-recovery evidence. `development-scope.md` gives requirements before broader
repository/tool access. Codex/Claude/OpenCode clients remain optional.

A command-transport interruption after hardware success delayed documentation;
the failed write never created a process. Normal computer re-selection restored
command access without host/service restart or permission changes. This did not
invalidate the already written private test records.

Assistant launch selection: gpt-6.1-sol; independent runtime model metadata was
unavailable. Hardware requests explicitly selected Flash, Coder Next and
GPT-OSS120B. No GPT-6 Luna was selected for this implementation task.
