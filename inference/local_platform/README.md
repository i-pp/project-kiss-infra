# Local inference client (provisional name)

A standard-library-only client for the existing guarded GPU Router. It does not
need Codex CLI, Claude Code, a paid API, AceIS daemon or MCP. The endpoint and unit
still have their existing compatibility names; no product rename is implied.

Useful now:

- Select Flash, Coder Next or GPT-OSS 120B without bypassing resource/switch guards.
- Submit once, poll, inspect or cancel a job, including after an uncertain outcome.
- Repair small pure Python functions against declarative cases, without executing
  arbitrary shell, model-proposed imports or executable test files.

## Run with an already accepted local service

This client procedure assumes the GPU service in `../aceis_service/README.md` is
already configured and healthy. It is not a fresh-host installation guide. Run
from this repository root, with Python 3.11+ on Linux:

```sh
SOCKET="$XDG_RUNTIME_DIR/aceis-inference/service.sock"
python3 -B -m inference.local_platform.cli --socket "$SOCKET" status
python3 -B -m inference.local_platform.cli --socket "$SOCKET" models
python3 -B -m inference.local_platform.cli --socket "$SOCKET" ask \
  --model gpt-oss-120b --prompt 'Explain one cause of a Python KeyError.' \
  --max-tokens 256 --timeout 180 --output /NEW/answer.json
python3 -B -m inference.local_platform.cli --socket "$SOCKET" get JOB_ID
python3 -B -m inference.local_platform.cli --socket "$SOCKET" cancel JOB_ID
```

Choose a genuinely new output path, or omit `--output` for JSON on stdout. Code
sent by `ask` is advice only, not applied or executed. Length-capped output may be
incomplete. Generation is never silently retried. Ctrl-C requests cancellation
once and reports `stop_confirmed:false`; use `get` to check the terminal state.
A lost submit reply may leave an accepted job with no client-known ID. Do not
blindly repeat that request. The server's deadline still bounds it.

## A bounded repair loop

The input source is never overwritten. The work directory must not exist:

```sh
python3 -B -m inference.local_platform.cli --socket "$SOCKET" repair \
  --source inference/local_platform/examples/calculator.py \
  --cases inference/local_platform/examples/cases.json \
  --workdir /NEW/private-repair-run --model gpt-oss-120b --attempts 2
```

The client runs a baseline, asks the selected local model for a complete candidate,
checks a small AST grammar, writes canonical UTF-8 from the validated AST, and runs
cases. On a test failure it sends the diagnosis into the next attempt, at most
three attempts. Transport uncertainty stops the loop rather than resubmitting.
`result.json` records actual test exit status and the accepted candidate is
`candidate.py`. Passing the supplied cases is evidence for those cases only.

This is useful for arithmetic/list/dictionary pure-function bugs. It is **not a
general repository agent** and does not fix arbitrary Python packages. Accepted
source contains only functions with unchanged positional signatures, arithmetic,
comparisons, local assignment, if/return, collection literals/subscripts and a
small set of pure builtin calls. No imports, attributes, decorators, private names,
loops, arbitrary calls, file/network/process APIs or executable tests are allowed.
The correct expression is not hard-coded into the validator. JSON cases use
`function`, positional `args` and `expected`; values are bounded primitives.

AST validation is not advertised as an arbitrary-code sandbox. Only this narrow
language runs in a child with CPU 3s, address space 256MiB, output file 1MiB and a
10s wall deadline. Canonicalization strips encoding cookies and comments before
execution. The trusted runner uses Python isolated mode and a minimal environment.
Tests, logs and candidates stay in the new private directory. Do not put secrets
in source or test data. There is no automatic original-file writeback or commit.

## API and remote boundary

The product-independent contract is [API.md](API.md). It uses HTTP/JSON over the
operator's owner-only Unix socket, with one GPU queue for all three models. A
missing NPU is reported separately and does not stop GPU requests. NPU inference
is still a separate service contract, not a GPU generation route.

This acceptance used one EVO-X3 as logical server and client. Two physical PCs,
WSL, LAN authentication and a remote transport are **not yet verified**. This
change opens no TCP port, creates no credentials, changes no SSH or firewall
settings and adds no cloud control plane. Do not point the CLI directly at
Ollama: doing so bypasses admission, layer limits, cancellation and release guards.
Codex/Claude Code/OpenCode compatibility is optional follow-up work, not P0.

## Tests

```sh
python3 -B -m unittest inference.local_platform.test_cli \
  inference.local_platform.test_repair -v
```

The Unix-socket unit test needs a host execution context that permits a private
local socket. The pure validator and repair tests use no model or network.
See `acceptance-20261107.md` for the separate hardware-backed result and limits.
