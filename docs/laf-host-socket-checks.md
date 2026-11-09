# Host-terminal check for the frozen 39 socket tests

## Busy-reader summary

This runner is for an authorized EVO-X3 execution environment that permits
private AF_UNIX sockets. After the Owner's access change/restart and a separate
successful access check, its corrected 39-test run passed. Do not infer permission
to retry elsewhere or change security settings from this result.

Use the exact reviewed runner commit from the delivery report. From this checkout:

```sh
python3 -B scripts/run-laf-socket-checks.py --runner-commit RUNNER_COMMIT --plan
python3 -B scripts/run-laf-socket-checks.py --runner-commit RUNNER_COMMIT \
  --evidence "$HOME/workspace/laf-socket-evidence-$(date -u +%Y%m%dT%H%M%SZ)"
```

Replace RUNNER_COMMIT with the full reviewed 40-character local commit. The plan
command performs local Git reads only and runs no tests. The second command is
for the host terminal, not the restricted executor. It refuses an existing
evidence directory. Python 3.10 or later and Linux are required; no package
installation, sudo, network or special privileges are needed.

Expected success: exit 0, `selected_suite_passed:true`, and 39 tests run with
zero failures, errors, skips or expected/unexpected successes in result.json.
Anything else is incomplete or failed. A failure is never automatically retried.
Do not delete evidence to make a later attempt look like the first run.

## Boundaries

- Runtime/test source comes from local Git commit
  08b4fb61e9d16319fa0e09a77321caa86254a6a0, not a mutable working directory.
  The launcher/worker are checked against the explicit runner commit.
- The exact frozen 39 test IDs use fake providers and temporary private Unix
  sockets. They do not invoke actual LLM, GPU/NPU inference, Docker or services.
- A short mode-0700 /tmp directory avoids Unix socket path-length overflow.
  It is cleaned only after the child stops and evidence is retained.
- The worker has a 120-second wall deadline, 60 CPU seconds, 2 GiB address-space
  limit and 8 MiB per-file output limit. The launcher allows up to 3 seconds
  each for TERM and KILL of only its new child process group. These are bounded
  waits, not hard real-time guarantees for a broken OS/kernel.
- A minimal child environment and audit guard block external process execution,
  TCP sockets and socket connections or mutations outside private scratch. The
  guard is protection against accidental calls by this reviewed suite, not a
  general security sandbox for untrusted Python. No production socket is used.
- Evidence includes plan.json, the exact source snapshot, tests.log and
  result.json. Before/after snapshot hashes are endpoint comparisons, not proof
  of continuous immutability. Existing host configuration and data are untouched.

A 39-test pass is not a complete integrated-suite pass, current-tree container
acceptance, native-runtime/hardware acceptance, second-PC E2E, clean-host
installation or public-release approval. Compare its frozen source identity with
other verification records before combining coverage claims.

## First host result and fixture correction

The original d867df7 runner completed all 39 tests in 18.4 seconds: 38 passed,
one failed, with zero errors/skips. The failure was test_public_parent_refused.
The worker's private umask 077 filtered mkdir(mode=0755) into 0700, so the test
had not created its intended public directory. The service's owned-0700 guard
correctly accepted that private parent; its security boundary was not changed.

The isolated correction explicitly chmods only the new temporary fixture to
0755 and asserts its mode before checking rejection. A socket-free regression
calls that same method with listener construction mocked out, under umasks 022,
027 and 077. It reproduced the original defect at 077 and passes after the fix;
an independent review confirmed the result. Original host evidence is preserved
with hashes in release/laf-socket-host-diagnosis.json. That original result stays
failed. The corrected run was subsequently executed as described below.

Do not reuse the old exact command to test this correction: it deliberately
pins the old source. Any later requested host run must use the revised runner
and its reviewed source pin, retaining a new evidence directory.

## Restored-access result

Runner 13e93aa with frozen source 08b4fb6 completed all 39 unique socket tests:
zero failures, errors or skips, 17.699 seconds in the test log and 17.833 seconds
launcher elapsed. Child termination and endpoint snapshot hashes were confirmed.
The later full integrated Python run on 13e93aa passed all 457 unique tests,
including these 39, in 25.543 seconds with no omissions. Independent read-only
review matched the logs, counts and source fingerprints to their Git objects.

This closes the recorded Python/socket verification gap. It does not close
runtime/model, native hardware, second-PC, clean-host or public-release gates.
