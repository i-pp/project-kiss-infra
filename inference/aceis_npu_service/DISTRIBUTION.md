# NPU build provenance and future container distribution

Status: **private design and working-host build only**. The future free Docker Hub proposal is a separate local-LLM + NPU development foundation, not publication of AceIS itself. Current AceIS work continues independently; this document provides technical/redistribution research for that separate idea and does not authorize publishing this repository, implementation or any runtime image. No registry push, public image, driver installation, device-permission change, or container NPU acceptance has occurred. A new private user service is deployed and tested separately; existing services remain unchanged.

## What was actually built

- The new `worker.cpp` was compiled locally with C++17 against the retained SDK's ONNX Runtime C API headers and linked dynamically to its ORT library. The complete command is in `build.sh`; it uses `-O2 -Wall -Wextra -Werror`, a literal `$ORIGIN` RUNPATH, and refuses to replace an existing output. The launcher supplies the exact library order. The final worker was built with Ubuntu g++ 15.2.0-16ubuntu1 and Python adapter syntax/tests ran on Python 3.14.4. Final worker SHA-256: `834acecb5de39577697fb053532b787dcf7c48169cc1956f340e6d142971b120`. It does not statically embed vendor libraries.
- The Python adapter uses only the standard library. It does not import the vendor Python wheel, so the previous Python 3.14 extension ABI issues are not prerequisites of this C API path.
- **ORT, the VitisAI EP/compiler, SDK Peano and local XRT were not built from source in this task.** They are retained prebuilt SDK/archive/extracted-package artifacts. A working custom C++ application is not a reproducible source build of the vendor runtime.
- Local XRT lives outside system packages and is selected per process. The final live worker's `/proc/PID/maps` confirmed actual `libxrt_core.so.2.25.37`, `libxrt_coreutil.so.2.25.37` and `libxrt_driver_xdna.so.2.25.260102.56.release` from the local XRT root, not system XRT 2.21.75 or the 2.19.184 copy found inside the retained voe wheel. Coreutil SHA-256 is `acbc609939c35e9edc0aed3709a0b5bdc6d0b9e5f53e9e6d2e0a94100ada2e97`; XDNA plugin SHA-256 is `f93fa0af14984dbd8105765e8ecd9847ab408eb770d2636aee6d31f8980601d8`. Three installed/retained version families must not be collapsed into one runtime claim. System XRT remains installed and unchanged for other work.

## Inputs and known provenance

The inspected local inputs are Ryzen AI SDK 1.8.0, `onnxruntime.tar.gz`, `llvm_aie-1.8.0-...whl`, quicktest assets, and the RAI 1.8 Linux NPU XRT package set. Prior retained inventories identify ORT 1.27.0, SDK Peano 21.0git, local XRT 2.25.37 plus its XDNA user-space plugin. The two ORT C headers match the official ORT v1.27.0 header blobs. The model hash is pinned in the service and README.

The prior evidence repository has a current-input hash baseline for selected retained containers, dependency inventories and a safe staging/preflight workflow. Its hashes identify current bytes, **not** a vendor signature, proof of historical acquisition, or proof of a clean-host source build. The original outer SDK download URL/receipt, exact historical build/install commands, complete outer-to-inner correspondence and reproducible source recipes for all binary components have not been established here. Do not invent or replace them with generic `cmake` commands.

For an independent rebuild of our application on a compatible, already provisioned host:

1. Acquire the SDK/XRT through the vendor's authorized route and review the applicable terms. Record version, origin, hashes and license documents; do not pull arbitrary third-party repacks.
2. Stage only the C headers, ORT/EP runtime graph, matching SDK Peano, XRT core/coreutil/XDNA plugin and pinned model in a new private tree. Preserve original inputs.
3. Check ELF `NEEDED`, SONAME, symbol versions and RPATH/RUNPATH with `readelf`, then resolve the complete library graph. A link or `ldd` of the worker alone does not cover later `dlopen` of compiler/EP/plugin libraries.
4. Run `build.sh SDK_ROOT NEW_OUTPUT`, capture compiler identity/version and binary hash. No `pip install` is required for this worker path.
5. Run the bounded CPU/NPU hardware probe from README, preserve its private logs/profile/ioctl trace and result. Establish actual driver submissions, internal CPU partitions and numerical comparison. Revalidate on every new runtime/host baseline.

This is a working-host rebuild procedure. It is not a verified clean-install Quick Start or a source recipe for the vendor stack.

## License findings and release gate

Read-only inspection of retained wheels found:

- `onnxruntime_vitisai-1.27.0-...whl` and `voe-1.8.0-...whl` metadata say `License-Expression: MIT`.
- Their actual `.dist-info/licenses/LICENSE.txt`, and that of `vitis_aie_essentials-1.8.0-...whl`, instead say use agrees to the [AMD EULA](https://account.amd.com/content/dam/account/en/licenses/download/amd-end-user-license-agreement.pdf) and [Ryzen AI third-party notices](https://account.amd.com/content/dam/account/en/licenses/download/ryzen-ai-1.7.1-linux-tpn-license.pdf).
- This inconsistency means **metadata's MIT label is not sufficient redistribution clearance**. The referenced third-party filename is 1.7.1 while the retained wheel is 1.8.0; the applicable complete license set needs confirmation.
- The SDK's bundled compiler, Peano, XRT binaries/plugin, firmware, and quicktest model each need the applicable license/source/notice/redistribution assessment. No separate model-redistribution grant was located in the bounded quicktest inspection. General ONNX Runtime upstream MIT terms do not automatically license every AMD bundled component or model.

The linked agreements have not been accepted anew or fully legally analyzed by this task. Before any public image: confirm exact redistributable subset, required notices, source-offer obligations if any, export/use restrictions if applicable, and the quicktest model's permitted redistribution. Obtain explicit publication approval. If unclear, distribute only our source/adapter image and require each user to obtain their own authorized SDK/runtime/model locally.

## Host requirements do not disappear in Docker

Observed working host: x86_64 EVO-X3, Ryzen AI MAX+395, NPU PCI `1022:17f0` / `0000:67:00.1`, Ubuntu 26.04.1, kernel 7.0.0-42, kernel amdxdna, firmware 1.1.2.65. The container shares that host kernel, firmware and physical NPU; it is not an independent driver bring-up.

Verified host packages at the final build: libc6 2.43-2ubuntu2.4, libgcc-s1 16-20260322-1ubuntu1, libuuid1 2.41.3-3ubuntu2.2, libzstd1 1.5.7+dfsg-3, libncurses6/libtinfo6 6.6+20251231-1, linux-image/linux-modules-7.0.0-42-generic 7.0.0-42.42, and linux-firmware-amd-misc 20260319.git217ca6e4-0ubuntu1.1. Package labels are observed provenance, not a command to downgrade or alter this working host.

The runtime needs the exact local XRT 2.25.37 selection, SDK ORT/compiler/Peano graph and ordinary-user access to `/dev/accel/accel0`. Host libc/libgcc/libuuid/libzstd/libncurses/libtinfo and the SDK-selected libstdc++/zlib must resolve compatibly. The retained static inventory identified 23 objects and 109 declared dependency edges; ABI and dynamic loading still require live acceptance. Do not substitute system XRT 2.21.75 simply because SONAMEs match. Earlier SDK success/failure differed with runtime selection, and compile-only mode is not NPU success.

## Proposed portable layout, not yet validated

- Public image candidate: only our code, standard Python runtime and our compiled worker **if** its applicable licenses allow distribution. No SDK/model/cache, host secrets, or raw traces. Pin base-image digest after selecting and testing a compatible userspace; no base image is claimed tested yet.
- User-owned SDK/model/XRT mounted **read-only** at a stable path, with service args selecting that path. Keep private cache/tmp/run directories writable and outside the SDK. Do not bake private absolute host paths into images.
- Pass only `/dev/accel/accel0` and the necessary render group mapping to the non-root container; never `privileged`, all of `/dev`, a Docker socket, host PID namespace or security-profile disabling. If group/device access is insufficient, stop and ask for the smallest approved host change; do not `chmod` the device automatically.
- A private shared Unix-socket directory with explicit UID and 0700/0600 ownership connects Router and NPU containers. No port publication. NPU health/readiness stays optional and separate from GPU readiness. No dependency chain in which an NPU failure stops Flash or Ollama.
- Set memory/CPU/pid limits after measuring cold compilation and steady state. Reserve headroom against Flash+one high-offload Ollama model and the desktop. Small model file size is not a bound on compiler memory.
- Container acceptance must repeat source build, library-selection evidence, CPU/NPU numerical probe, real accel ioctl evidence, shutdown/child cleanup, NPU outage with GPU still serving, restart recovery and concurrent-load memory measurements.

Open gates: exact runtime/source-build provenance; complete redistribution permissions; compatible pinned base userspace; container device/group access without host security changes; measured cold/steady memory; containerized real-NPU and co-load acceptance. Until those pass, a Docker Hub artifact would be an unverified distribution, not a portable supported NPU service.
