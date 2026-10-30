# SGLang AITER startup failure: actual source read before one bounded continuation

Runsglang-393355304b41496797f86bb5bdc23f24 completed after78.118seconds with environmentFAIL/qualityUNASSESSED/generation0. The server exited at64.985seconds during quantization registry import, with ModuleNotFoundError foraiter.jit.module_aiter_core. The ownedcontainer was terminal/removed per savedhostrun, sourceweight metadata unchanged and30Brestored. OuterMCP independently confirms30B-onlyREADY/blocked_uncertainfalse and daemonidle. The operator's one model-start attempt is consumed; do not delete/reset/reuse it.

Logs show AITER JIT build under/tmp/aceis-home/.aiter/jit/build/module_aiter_core, then repeated qualifiedaiter.jit imports fail. General/tmp isnoexec and image root isreadonly under the approved profile. Those observations suggest cache/search-path mismatch, but noexec is not proven as the direct cause: the actual exception is missingmodule, not a recorded executable-mapping errno. amdsmi/dlpack warnings are not the finalexception. The temporary/tmp artifacts were removed with the container and cannot now be inspected retrospectively.

Upstream fixed AITER source c16d44b93a528b2a4bfd6d8d3409116d465872a9 supports AITER_JIT_DIR, adds that directory tosys.path and changes module import to the unqualifiedname when present. Source: https://github.com/ROCm/aiter/blob/c16d44b93a528b2a4bfd6d8d3409116d465872a9/aiter/jit/core.py#L426 . This pin occurs in the older official gfx1151recipe and publicimagehistory, but actual image-file equality is not yet attested. It is a supported hypothesis, not a claimedfixsuccess.

The small offline candidate changes onlySGenvironment toAITER_JIT_DIR=/jit-cache/aiter. It keeps Triton at/jit-cache/triton, both inside the existing512MiBexecmount. General/tmpnoexec/nonroot/nnp/read-only/caps/network and all model/time/resource budgets remain unchanged. Candidate105CPUtests and independent review passed. This candidate is not installed in the active trialrunner and no additionalmodelstart has occurred.

## Next real source-only step

User continuation Sentinel_c374855f7b308191a87d9a41e921de2e permits stoppingllama and continuing finitevalidation, without newsecurityboundaries. The source-only check itself leaves30Brunning and needs no modelstart. From a normalhostterminal:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/sglang_content_handoff/inspect_aiter_source_host.py --inspect-human
```

This reuses the existing fixed officialimage and nativehostguard. Dockeraccess from the selectedCodex route is deniedEPERM, so this exact nativehoststep cannot be substituted by agent-sideDocker/escalation or anotherbroker. Python/fileanalysis remains available inCodex.

OneCPU-onlycontainer reads4fixedimagefiles asdata: AITERcore/extension/init and SGLangQuark source. It imports onlyPythonstdlib under-I-S-B, neverAITER/Torch, nevercompiles and has noGPUdevices/network. ExistingCPUprofile is256MiB/no containerswap/CPU1/PID64/read-only/nonroot/capdrop/nnp/tmp16MiBnoexec. Imageinspect is15seconds, sourceprocess30seconds, absencecheck10seconds. The samecommon generationlock serializes this short check. No model/route/hostsetting is changed.

An owner-onlyreceipt includes fixedimageidentity, actualfilebytes/SHA, selectedfunctionbodies and boundedrelevantglobalassignments asuntrusteddata. Source support is not guessedfromversion0.0.0. A successfulsourcecapture is not runtimeor importsuccess. The ownedCPUcontainer must be confirmedabsent; an uncertainoutcome writes a wrapper-specific no-retrymarker, not a claim that allGPUentrypoints are globallyblocked. Do not start the newmodeltrial until positiveabsence and sourceinspectionreceipt are verified. A previouspendingCPUintent withoutterminalreceipt also blocks this wrapper.

The source-reader/wrapper has6CPUtests and independentreview, with addedbd_dir/this_dir assignment capture. No actualcontainer has been run byCodex.

## Following bounded model continuation

After actualsource confirms the cache/search branch, prepare one newoperator tied to the continuation instruction, preserving the consumedoldoperator/run. The exactnewoperator must carry the already-approvedsame128MiB freshbaseline policy for this oneSGcontinuation; do not silentlybroaden backendpolicy or clear spentattempts. Model/context4096/max64output/temp0/seed42/1request, whole900/start300/generation90/recoveryreserve185,32GiBcontainer and existingGPU/RAM/security limits remain. Stopllama30B only within that trial, collectownedtarget and restore30B afterward. No newimage/weights/download/install/securitygrant is needed for this candidate. If512MiB fills or source does not support the expectedbranch, stop and report; no automaticexpansion or extra retry.

The continuation authorizes the necessary boundedprogress beyond the consumedattempt; it does not authorize newexecutions outside the fixedprofile. VLLM and Strata exceptions are not changed by this preparation. Their remainingphase/limits need separate plans rather than a blanketnewresourcepolicy.
