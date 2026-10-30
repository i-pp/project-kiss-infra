# Local LLM development backup checkpoint — 2026-10-30

This backup preserves backend preparation and local-LLM integration source/docs/tests from the existing private project-kiss-infra workspace. It is a recovery branch, not a deployment. Historical README/profile/checkpoint assertions are retained as historical development artifacts and must not be treated as current host health or new execution authorization.

Verified earlier: the existing llama.cpp router served30B, gpt-oss-120B and Qwen3-Coder-Next through ChatGPT MCP in separate finite calls, then returned to30B. This establishes connectivity, not general coding accuracy. Alternative-backend target inference remains incomplete: vLLM exited during startup, Strata full verification timed out, and latest SGLang loaded all10Next weight shards then failed allocating Mamba temporal state (17.86GiB request vs17.66GiB free). That trial sent0generation requests, cleaned up, and restored30B. The8GB total host-swap policy did not trip. Original raw evidence is deliberately excluded.

Proposed next SGLang change is --max-mamba-cache-size8, source-derived estimated state pool663.1875MiB, ordinary4096-token full-attention KV96MiB. Image source equivalence and a new finite trial remain unverified/unapproved; no attempt is granted here. Inert, unapplied guard/logging proposals are under docs/proposals/codex-host-guard.

Four source/config/proposal files contained this machine's full paths. Only this backup copy substitutes PROJECT_ROOT/ORCHESTRATOR_ROOT placeholders. local_llm.policy_context fails closed until the canonical project path is restored explicitly. The original live files, configuration, services, attempts and logs were not edited. Do not run model/GPU/deployment/recovery scripts as a restoration side effect.

Excluded: runtime databases/receipts/credentials/keys, raw logs and evidence, models/checkpoints, caches, native SDK or engine binaries, screenshots, and unrelated dirty evaluation/B4/B5 files. Historical one-off evaluation originals were not regenerated or modified. Assets/runtime manifests here are text identity/plan fixtures, not downloaded binaries or credentials.
