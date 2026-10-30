# Separate SGLang runtime acquisition approval proposal — not executed

Request acquisition only of the official AMD Verified Publisher linux/amd64 image:

`rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230`

Tag `v0.5.22-rocm724-gfx1151-20261029`; registry compressed total13,667,503,350 bytes. The public registry metadata is linked in SGLANG_RUNTIME_FINDINGS.md. Expanded disk size is not yet measured; require64GiB free before acquisition and record actual Docker image size afterward. No claim of a hard extraction quota or known expanded size. Existing shared Next weights need no new download.

SGLang v0.5.22 source candidate `baa9befa381511cd4d56f83980951e5a45fffc6d` is Apache-2.0. Image source exact commit and full bundled/base/component notices must be checked after acquisition; public build history is consistent with ROCm7.2.4, torch2.9.1, Triton3.5.1, compressed-tensors0.15.0, AITER disabled. This is not full-image license/source attestation or actual kernel support proof.

Human host operation after separate approval is a fixed-digest `docker pull` only, followed by read-only identity/size inspection. No GPU devices, model mounts, container launch, service/security/group/driver change, new credentials, or automatic30B stop is included. Do not use sudo/newgrp/context changes for a permission failure. No API charges; network transfer/storage only. Timeout/interruption is an uncertain acquisition state to inspect before repeating.

```text
docker pull rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230
docker image inspect rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230 --format '{{json .Id}} {{json .RepoDigests}} {{json .Size}} {{json .Config.Labels}}'
```

Runtime/source/dependency verification and a separately planned finite1POST GPU trial remain pending. The previous Strata and Next approvals do not cover this image acquisition. There is no source/runtime bootstrap record marking it READY.
