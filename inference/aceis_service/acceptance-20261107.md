# EVO-X3 acceptance, 2026-11-07

## Outcome

The new `aceis-inference.service` is active/enabled in the user's systemd manager.
Strata Flash is resident and the Router has successfully served Flash, Coder Next
and GPT-OSS 120B through its private Unix socket. Ollama loads at most one large
model. Source models, historical containers, existing daemon, MCP HTTP adapter,
Tunnel, Events and desktop notifications were preserved.

Existing production AceIS daemon/MCP routes have not yet been switched to this
new socket. The supplied client is an explicit opt-in boundary. This acceptance
therefore establishes the service, not automatic production-MCP wiring.

## Versions and identity

- GPU: Radeon 8060S/gfx1151, 64 GiB firmware-reserved UMA VRAM.
  OS MemTotal is about61.43 GiB; GTT is not additional physical RAM.
- Strata live engine0.1.52 HIP. Executable SHA256:
  `d236d8829e682c26571ae8734fb2b69b8f1abf9c728dbb2e990aa21686d1071c`.
- Ollama live API0.40.15, existing offline image
  `sha256:d4ae7c574945c7432c8c02ae63fa81ad555854d9fcbc29d02542a4dd69833a85`.
- Coder Next Q4_K_M:48 requested GPU layers. GPT-OSS120B MXFP4:28.
  Context configured8192, output limit1024.
- Existing weight sizes were inventoried. This work did not rehash every large
  GGUF, so prior weight digests are historical evidence rather than new hashes.
  The unpacked Strata source has no independent Git HEAD; the containing
  project's Git HEAD is not claimed as Strata provenance.
- Engineering execution was launched with `gpt-6.1-sol`; independent runtime
  model metadata was unavailable. No GPT-6 Luna execution is asserted.
- Canonical operating policy commit
  `394bf5377c2b82bb6f660ca917192bdbe337bc85` was read through the verified loader.

## Performed checks

`python3 -m unittest inference.aceis_service.test_service -v`:26 core/backend/HTTP tests passed on
EVO-X3. These cover input bounds, malformed types, single-lane queue/cancellation,
resource latch/recovery, UDS HTTP, Origin/Host checks, actual RAM/VRAM release
barriers with injected telemetry, changed-container rejection, restart readiness,
swap-I/O guards, stop-failure latching, stale-cancel stop ordering, and child-group
termination after wrapper exit. Compilation and Git whitespace checks passed.
The repository's unrelated Docker evaluation suites were not run.

An independent read-only technical review identified lifecycle, ownership,
shutdown and schema issues. The fixes were re-read and the reviewer confirmed no
remaining startup blocker in that scope. The reviewer independently checked AST
parsing/malformed inputs/test discovery; the live tests below were performed by
the implementation worker, not by that reviewer.

Monitored foreground API acceptance, wall time includes load/switch when present:

| Stage | Actual prompt/output tokens | Wall seconds |
|---|---:|---:|
| Flash short |28/128|6.32|
| Next initial load |24/128|14.71|
| Next→120B |82/128|27.44|
|120B→Next |24/128|15.38|
| Next longer input/output |930/512|11.40|
| Flash six consecutive requests |23/128 each|3.92–5.13|
| Next in NPU test window |18/512|10.44|

All named generations reached the
configured output cap (`length`). No general answer/code-quality pass is claimed.

Foreground monitoring sampled302 times at0.5s intervals: OS available RAM minimum
37.14 GiB, VRAM maximum51.25 GiB, swap usage unchanged within that run, swap-in/out
increments0, memory full PSI avg10 maximum6.2%. The broader preparation/restart
workload did cause a small swap increase, below the configured512 MiB guard; the
zero-swap statement applies only to that monitored foreground window.

Cancellation of an active Next request reached `cancelled` in4.05s, stopped owned
providers, and a subsequent Flash request completed. Normal foreground SIGTERM
returned exit0 with VRAM about0.862 GiB and GPU use0%. Flash remained resident
through successful Next/120B switches and was intentionally recreated after
cancellation.

An additional live fault injection terminated only the owned native Flash engine
while its tokenizer wrapper remained alive. Health became not-ready, automatic
bounded recovery replaced both wrapper and engine in3.39s, and a subsequent
Flash64-token request completed. Engine health now verifies the native child in
the owned session/group, rather than treating a living wrapper as readiness.

## systemd acceptance

- New user-unit Flash request:20/64 tokens,2.77s.
- Restart changed MainPID and reached ready in4.98s.
- After restart: Next15/64 tokens12.44s;120B75/64 tokens21.54s.
- A longer structured hexadecimal-data request on120B used3506 prompt tokens and
  produced256 output tokens in14.93s. Full8192-token input acceptance is untested.
- The third manual start within600s was refused by configured StartLimitBurst2.
  Only this new unit's failed/start counter was reset for the controlled test;
  the guard was not weakened.
- Stopping0.2s into initialization completed with VRAM0.896 GiB. A subsequent
  fresh start reached ready and the new unit was enabled.
- Final state: Flash ready, no large model selected, no host TCP inference port.
  Private directory0700/socket0600 and same-user peer check were confirmed.
- Existing AceIS daemon/adapter/Tunnel/Events/notifications remained active.

A user-service restart was tested. The host was **not rebooted**, and user-manager
lingering/login/security settings were not changed. Reboot persistence without a
running user manager is not established by enabling a user service.

## NPU coexistence

The independent NPU service was healthy through its own private socket. The GPU
Router reported its status without making GPU readiness depend on it.

GPU API completion was logged at08:09:17.7796Z with10.42s duration, giving a start
near08:09:07.36Z. NPU requests beginning08:09:07.974Z and08:09:08.482Z were within
that GPU request interval and succeeded. The first NPU request began near the GPU
start boundary and is not separately asserted as fully overlapping. This was a
short coexistence check, not a throughput or long-duration stability conclusion.
The NPU worker records actual VitisAI/mixed CPU execution separately.

NPU worker failure/recovery was also injected by the NPU owner. During the actual
not-ready interval, GPU health stayed ready and a Flash64-token request completed
in3.06s. NPU then became ready again without restarting the GPU service. This
checks independent availability, not simultaneous failure recovery under pressure.

## Remaining acceptance and distribution work

- Production AceIS MCP wiring must be verified separately without interrupting
  active tasks. The new service does not change existing auth or tool policies.
- No machine reboot, multi-day soak, multi-user workload, full8192-token prompt,
  concurrent Flash/large generation, or three-model residency test was performed.
- Continue longer soak and fault-injection under real usage before calling this
  a general unattended-production reliability pass.
- Private imports consume about112 GB and are retained for restart. Source weights
  were not removed. No packages/drivers/BIOS settings were installed or changed.
- No image/release was published and no PR was merged. Future Docker Hub
  reproducibility and redistribution prerequisites are in `distribution-notes.md`.

Extended unattended acceptance is tracked in private issue3:
https://github.com/i-pp/project-kiss-infra/issues/3
