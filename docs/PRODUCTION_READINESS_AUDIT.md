# EuroClaw — Production Readiness Audit

This document tracks the gap between EuroClaw's stated pillars and the actual
implementation, and records what was remediated in v0.2. It is deliberately
candid — treat any ❌ as a hard blocker for regulated production use.

## Summary of v0.2 remediations

| Area | v0.1 state | v0.2 state |
|---|---|---|
| Packaging | `pip install -e .` installed nothing; README examples unrunnable | ✅ Real `euroclaw` package; `pyproject` metadata; console scripts |
| Reasoning loop | Returned raw LLM text; **never executed tools** | ✅ Wired reason→act→observe loop with bounded iterations |
| LLM failure behavior | Fabricated a destructive `rm -rf` tool call | ✅ Fails closed with `LLMUnavailableError` |
| RBAC | Claimed but unenforced | ✅ Enforced on every tool call; env-overridable policy |
| Sandbox | `execute_tool` returned a hardcoded string (no execution) | ✅ Pluggable backends; subprocess actually executes + isolates |
| JWKS | Fetched from IdP on every request | ✅ Cached with TTL |
| MCP subprocess env | Inherited entire parent env (secret leak) | ✅ Explicit env allowlist |
| Rate-limit / HITL state | Per-process dicts (broken across replicas) | ✅ Redis-backed with in-memory fallback |
| Request path | Blocking `.get()` / `sleep()` on the event loop | ✅ Async run model + threadpool; SSE streaming |
| Readiness probe | Always returned 200 | ✅ Returns 503 on invalid config / missing Redis (distributed) |
| Telemetry | Disabled by default in the image | ✅ On by default; degrades gracefully |
| Audit | Mermaid `.md` only | ✅ Hash-chained append-only JSONL ledger + OTel spans |

## Known limitations / operator responsibilities

- **Firecracker backend is not exercised in CI** (needs KVM hardware, a kernel +
  rootfs image, and a vsock guest agent). The host-side code is implemented and
  fails closed (`SandboxUnavailable`) when `/dev/kvm` is absent. Validate it on
  your KVM hosts before relying on hardware isolation.
- **`subprocess` sandbox is process-level, not a kernel boundary.** On Windows
  resource limits are unavailable. Do not run fully untrusted code under it in
  production — use `firecracker`.
- **Redis** must be authenticated + TLS in production (`REDIS_PASSWORD`,
  `REDIS_USE_TLS=true`) and should be highly available. It is a hard dependency
  for multi-replica correctness.
- **Audit ledger** is local by default; point `AUDIT_DIR` at WORM storage and
  ship OTel spans to an immutable backend for EU-AI-Act evidence.
- **Container base image** may carry upstream OS CVEs; rebuild on a hardened base.
- **Secrets** must come from a managed store (Vault / cloud secret manager), never
  committed `.env` files.

## Recommended pre-production checklist

- [ ] OIDC issuer/audience point at your IdP; tokens validated end-to-end.
- [ ] `RBAC_POLICY` reviewed and mapped to your SSO groups.
- [ ] `SANDBOX_BACKEND=firecracker` validated on KVM hosts (if running untrusted code).
- [ ] Redis authenticated, TLS-enabled, HA.
- [ ] OTLP collector + immutable audit sink wired.
- [ ] Rate limits tuned; reverse proxy terminates TLS.
- [ ] Load test the async run API and HITL flow.
