# Optional RyzenAI classification service

## Busy-reader summary

This is a private Unix-socket service with one persistent ONNX Runtime C API session. It is independent of the GPU Router's process and readiness. The pinned SDK quicktest classifier takes **3072 float32 values**, shaped `[1,3,32,32]`, and returns ten logits and their argmax. It is a **plumbing validation classifier**: label meanings, training provenance, accuracy, and application preprocessing have not been established. Do not use its class index for a real-world decision.

On EVO-X3, fresh execution confirmed the real NPU command path, with identical CPU/NPU logits for one synthetic input. Execution is **mixed NPU and CPU**, not entirely NPU: the VitisAI compiler reports one DPU subgraph and one internal CPU subgraph for output dequantization. Disabling ONNX Runtime CPU EP fallback does not disable VitisAI's own CPU work.

```bash
python3 -m unittest discover -s inference/aceis_npu_service/tests -v
bash inference/aceis_npu_service/build.sh "$SDK" "$PRIVATE_BUILD/worker"
curl --unix-socket "$XDG_RUNTIME_DIR/aceis-npu/service.sock" http://localhost/health
```

The first command needs permission to create Unix-domain sockets. The build requires an already installed compatible SDK and C++ compiler. These commands alone are not a clean-machine Quick Start. The working-host procedure below lists the retained prerequisites.

## Local validation commands

The Python regression suite currently has 16 tests, including shutdown of a TERM-ignoring descendant after its leader exits, deadline handling when the worker never reads stdin, private HTTP boundaries, explicit CPU identity, and rejection of misleading hardware traces.

The production C++ input parser also has a device-free boundary fixture:

```bash
c++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$SDK/cpp-test/include" \
  inference/aceis_npu_service/tests/test_parser.cpp \
  -L"$SDK/cpp-test/sdk/onnxruntime/lib" -lonnxruntime -o "$PRIVATE_BUILD/test-parser"
LD_LIBRARY_PATH="$SDK/cpp-test/sdk/onnxruntime/lib" "$PRIVATE_BUILD/test-parser"
```

This passes the smallest positive float32 subnormal and maximum finite float32 through the same decimal parser as the production worker. JSON input is rounded once to float32 before serialization. A boundary fixture is not a claim that extreme-valued model inputs always yield finite logits; nonfinite model outputs deliberately fail closed.

## Contract

- `GET /health`: 200 when the owned worker is alive and the warmup ORT profile proves the requested EP executed. Otherwise 503. It reports `execution_target`, `execution_scope`, `verification_kind`, internal CPU/DPU partition counts, model hash, ORT version, and profile hash.
- `POST /v1/classify`: JSON `{"model":"ryzenai-quicktest-10class","input":[...3072 finite float32 values...]}`. Response adds `logits`, `class_index`, and `latency_ms` for the worker's inference call. No image upload or automatic normalization is provided.
- HTTP 400 invalid input; 403 browser Origin; 413 over 100,000 bytes; 415 wrong content type; 429 another inference is active; 503 owned worker failure or its ten-second deadline. No request queue, retry, autoload, or implicit CPU fallback.
- `--provider CPU` is an explicit diagnostic mode. It reports `execution_target=cpu`, `execution_scope=cpu_only`; it is never reported as NPU.
- The socket parent must be owned by the current user and mode 0700; the socket is mode 0600. No TCP listener, new credential, external service, or tunnel is created. A preexisting socket is never deleted on startup.
- At most eight HTTP handler threads, one inference, 5-second connection read timeout. Health remains independent of inference serialization. Inputs and logits are not request-logged.

`execution_verified` specifically means **the warmup ran on the declared ORT execution provider**, not hardware counters, pure-NPU execution, or accuracy validation. The hardware probe below is separate evidence. `execution_scope=mixed_npu_cpu` makes internal CPU work explicit.

## Working-host launch and stop

Prerequisites already retained on this test host: Ryzen AI SDK 1.8.0, its ONNX Runtime 1.27.0 C headers/libraries, its matching Peano, local XRT 2.25.37, an accessible `/dev/accel/accel0`, and a compiler. No host package, driver, BIOS, permission, or global environment changes are made here. The system XRT 2.21.75 is not substituted for the local SDK runtime.

From the repository root, with no conflicting NPU workload:

```bash
SDK="$HOME/develop/npu/ryzen-ai-1.8.0"
PRIVATE_BUILD="$HOME/.cache/aceis-npu-build"
install -d -m 700 "$PRIVATE_BUILD"
bash inference/aceis_npu_service/build.sh "$SDK" "$PRIVATE_BUILD/worker"
# worker must be a NEW filename. Rebuild with a different filename; existing output is preserved.
RUN_PARENT="$HOME/.cache/aceis-npu-runs"
install -d -m 700 "$RUN_PARENT"
RUN="$RUN_PARENT/run-$(date -u +%Y%m%dT%H%M%SZ)-$$"
# RUN must not exist; the service creates it with mode 0700.
python3 -m inference.aceis_npu_service.service \
  --worker "$PRIVATE_BUILD/worker" --sdk "$SDK" \
  --xrt "$SDK/xrt-2.25.37/opt/xilinx/xrt" \
  --model "$SDK/cpp-test/samples/quicktest/test_model.onnx" \
  --run-dir "$RUN" --socket "$XDG_RUNTIME_DIR/aceis-npu/service.sock"
```

Leave this foreground process in an owned terminal, or use the optional user-unit template after reviewing its paths. Ctrl-C or SIGTERM to **this service PID** stops its worker process group and removes its own socket. Do not use broad `pkill` commands. Startup has one warmup and a 180-second timeout. Startup failure closes the owned worker and exits instead of switching to CPU. A dead worker after startup returns not-ready; there is no restart loop.

The worker gets a minimal, explicit environment: private HOME, cache, tmp, and working directory; local XRT then SDK ORT then matching Peano library order. It does not modify the retained SDK. `run-dir` must be a fresh directory. Binaries, SDKs, model, raw profiles, compiler caches, and private logs belong outside Git.

Example request:

```bash
python3 - <<'PY' > "$RUN/input.json"
import json
print(json.dumps({"model":"ryzenai-quicktest-10class", "input":[float(i%251)/250 for i in range(3072)]}))
PY
curl --max-time 12 --unix-socket "$XDG_RUNTIME_DIR/aceis-npu/service.sock" \
  -H 'Content-Type: application/json' --data-binary "@$RUN/input.json" \
  http://localhost/v1/classify
```

Router integration: configure only its optional NPU socket path. The GPU Router must not load the NPU model, supervise the NPU worker, or make GPU readiness depend on NPU readiness. NPU downtime is local to classification. GPU and NPU share system memory, so any co-load acceptance must record memory headroom and active workloads. No installed unit, enabled service, production Router modification, or auto-start is implied by this source template.

## Confirm actual hardware execution

EP registration alone is insufficient. The bounded EVO-X3 probe used a fresh private directory and the exact built worker/model/runtime environment above:

The complete working-host probe is:

```bash
python3 -m inference.aceis_npu_service.probe_hardware \
  --worker "$PRIVATE_BUILD/worker" --sdk "$SDK" \
  --output "$HOME/.cache/aceis-npu-probe-$(date -u +%Y%m%dT%H%M%SZ)-$$"
```

It needs an already installed `strace`, direct NPU access, and a fresh output directory. It runs once on CPU and once on NPU, with one warmup and one request per mode. Its acceptance threshold is exact equality for this synthetic probe, not a general model tolerance. No retry is performed.

1. Run one warmup and one synthetic inference under `strace -f -yy -e trace=ioctl -o PRIVATE/ioctl.trace`, with a 180-second timeout. Trace only a newly owned worker, not unrelated processes. The trace contains only ioctl metadata for this synthetic test. Do not commit raw traces.
2. Inspect the fresh ORT profile with `profile_evidence`: it must contain executed `VitisAIExecutionProvider` node events and no ORT CPU-provider events. Check compiler partitions separately; CPU work internal to VitisAI does not appear as CPU EP events.
3. Run `python3 -m inference.aceis_npu_service.verify_trace PRIVATE/ioctl.trace`. It requires successful `DRM_IOCTL_AMDXDNA_EXEC_CMD` and successful `DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT` on `/dev/accel/accel0`.
4. Compare all ten finite output logits to an explicit CPU-mode run with the same serialized input and model hash. Use an application-justified tolerance for other models/inputs. One matching synthetic sample is not model accuracy validation.

Do not bypass missing device access, relax kernel tracing/security settings, install a different driver, or reset the NPU to make the probe pass. Report the blocked stage instead. `/proc/PID/fdinfo` on this kernel exposed the accel fd but no engine counters; that was not treated as execution proof.

## Evidence: 2026-11-07 UTC

- Device: Ryzen AI MAX+ 395 / Radeon 8060S, RyzenAI-npu5 at `0000:67:00.1`, firmware 1.1.2.65, Ubuntu 26.04.1, kernel 7.0.0-42.
- Model: SDK `test_model.onnx`, SHA-256 `7a78c7e85bac3a0681e3d2f77e69093a761e1c8f62f7fc65ff5ce3e1b82c5ba3`, approximately 23 MiB. Vendor model/binaries are not redistributed.
- CPU profile: 360 CPU EP node events. NPU profile: three VitisAI EP node events, no ORT CPU EP events. ORT CPU fallback disabled. Compiler: one DPU and one internal CPU partition.
- Traced warmup + request: **two successful NPU EXEC_CMD submissions and two successful completion waits**. Trace SHA-256 `6591f8900c5e2ec766752b746bd7a04dd783c19081250f3584b5f2ec32d99417`.
- Same synthetic input: CPU/NPU logits exactly `[6.25,1,-0.25,-1.5,-2.375,-3.5,-2.125,-2.75,2,0.25]`, argmax 0. Absolute maximum difference 0 for this sample only.
- Observed worker call times: CPU 7.72 ms; NPU 1.62 ms; three further NPU calls 1.72/1.62/1.60 ms. These are tiny smoke samples, not throughput or tail-latency benchmarks. Startup compilation is excluded.
- Build: C++17, `-O2 -Wall -Wextra -Werror`. Host libraries and original SDK were not altered. Existing services were not stopped.
- Coordinated concurrent smoke: Flash stayed resident while Next generated 512 tokens from approximately 08:09:07.36 to 08:09:17.7796 UTC. NPU requests beginning 08:09:07.974 and 08:09:08.482 UTC fall strictly inside that GPU request; both returned HTTP 200 and unchanged logits. Worker calls were 2.39/2.30 ms, HTTP elapsed 7.99/7.58 ms. A first request at 08:09:07.342 was at the GPU start boundary, so overlap is not asserted for it; its idle-resume worker time was 125.43 ms.
- Available system memory at those NPU samples was at least 51,984,672 KiB (49.58 GiB). The persistent NPU worker's observed RSS/high-water mark was 749,952 KiB (about 732 MiB), plus a 26 MiB Python adapter. The 23 MiB model file is not a runtime memory budget. These are observed values, not exhaustive cold-start peaks or cgroup limits.
- The concurrent test used worker-v2. The final worker-v4 refactors the same parser for a boundary fixture and adds an explicit successful return. Its separate final hardware probe also passed: exact logits match, CPU 360/NPU 3 profile events, two successful accel EXEC_CMD and two completion waits; final trace SHA-256 `6408e621c99156825777f9b4bb023c0186b30f252eee26914820b96ece6d6c8f`. Traced NPU timing is diagnostic, not a performance benchmark. Long-running reliability, container acceptance, application accuracy and broad load/latency claims remain unverified.

## Implementation and review record

The implementation worker was launched with requested model `gpt-6.1-sol`. Actual runtime model metadata could not be independently inspected. Independent runtime-safety review identified and repaired group-cleanup, pipe-write deadline and trace-path exactness issues; the final regression suite and C++ parser fixture were rerun. This is engineering provenance, not proof of model-generated correctness.
