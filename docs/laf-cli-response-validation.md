# CLI response validation

The CLI now rejects ambiguous or malformed UTF-8 JSON responses before treating
them as service evidence. This local increment does not change or deploy Router
code, create a transport, submit inference, or retry a request.

- Reject duplicate keys at any level, non-finite numbers including overflowing
  exponents, non-object responses and nesting beyond 64 containers. String
  brackets and escaped quotes do not contribute to nesting depth.
- Convert invalid UTF-8/JSON and excessive decoder recursion to ClientError.
  UTF-16/32 and BOM-prefixed JSON are outside the UTF-8 wire contract.
- Reject malformed GPU/NPU health sections without an uncaught AttributeError.
- Check get responses against the requested job ID, a supported model and known
  state. Completed jobs must contain string content. Keep the known job ID on
  errors so the owner can reconcile it without resubmission.
- Accept cancellation only with cancellation_requested. This acknowledgement
  never proves the job or underlying inference stopped.

From this candidate directory, run the new entirely offline regressions:

```sh
python3 -B -m unittest inference.local_platform.test_cli_responses -v
```

All 25 new test methods pass. The final tests fail on the preserved baseline:
16 failure events and 12 error events across 25 methods, including subtests.
The selected client/model/workspace/project-runner/developer regression passes
196 test methods. One preexisting private-socket test was denied in the author's
executor and is explicitly omitted from that selected run. This is not a full
regression or live remote/hardware acceptance. No failed or unexecuted test is
counted as passed.

Independent review passed against the final source, including depth boundaries,
2,000 deterministic escaped/Unicode string cases and malformed numeric probes.
The reviewer separately observed the existing temporary-socket test pass in its
own executor before scope clarification; that does not repair or override the
author's denied execution.

This is not full route-schema validation or a total wall-clock read deadline.
The existing response byte bound and socket idle timeout remain unchanged.
Real PC-B connectivity, build/test E2E, remaining P0 and release gates remain open.
These test commands are not a Quick Start for a running service.
