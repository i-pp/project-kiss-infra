# Approved bounded local LLM MCP integration

Operator approval: 2026-10-29 08:50 UTC, verified by parent. Add exactly one operation
`aceis_local_llm_generate` (three metadata tools become four), localhost resident
`kiss-qwen3-coder-30b` only, serial, 90-second MCP wall bound, maximum 1024 output
tokens, necessary service reflection and one parent-run ChatGPT connector smoke.
No submit/cancel permission, new key, model loading, external listener, paid API,
new isolation, security-property change or login/reboot autostart is included.

The adapter uses default-off `--allow-local-llm` and a fixed trusted helper:
`<PROJECT_ROOT>/agents/local_llm/extension.py --call`.
The helper loads the current verified canonical common policy with the existing
loader, includes its full body, and refuses missing/invalid policy before HTTP.
Its whole-operation deadline is 85 seconds, leaving cleanup margin inside 90.

Arguments: task (`draft` or `review`), explicit prompt (1..16384 UTF-8 bytes), optional
max_tokens (1..1024, default 256). No file/path/command/endpoint/model/key arguments.
Results always carry `untrusted_advisory=true`, `verification_status=NOT_EXECUTED`,
`code_executed=false`. No returned code is executed. UNKNOWN is not automatically
retried; the private uncertainty marker blocks blind client retries.

The preserved PROPOSAL.patch records the adapter delta against base.json. Live
integration additionally adds explicit opt-in to the existing PoC service command.
Existing ownership nonce/InvocationID checks are used for Tunnel-only replacement;
the daemon, canonical policy, guard and existing fixtures are retained.

Verification boundaries:
- Two earlier Codex CLI/local-handler real calls passed; these preceded policy integration.
- 19 client offline tests include policy failure/context budget/shared deadline.
- External ChatGPT inference: LIVE PASS, parent single call `607930eb-fcf4-435c-b70d-b45942f01def`, 2026-10-29 09:19 UTC; exact ACK returned with verified policy attached.
- New B4 execution: BLOCKED_NESTED_ISOLATION_FORBIDDEN, no fallback or attempt.
- 120B: historical repair evidence only, not loaded/connected through this tool.

No generated code, namespace, new model, download, credential or host change is
used for integration. Do not treat tools/list or status as proof of inference.

The resident30B invocation setup is complete. The outer real Tunnel observed a
complete four-tool catalog after existing-app refresh. Local adapter audit matches
the parent connector call ID and end/returned. This is connection evidence only;
no general model quality or generated-code execution PASS is claimed. See README
for remaining 120B/Next connection and blocked B4 work.
