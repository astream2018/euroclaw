# 🇪🇺 EuroClaw

EuroClaw is an open-source, enterprise-grade **agentic AI framework** engineered for
**data sovereignty, zero-trust execution, RBAC governance, and horizontal scalability**.

It routes reasoning through **local** LLMs, enforces **role-based** access on every
tool call, gates high-risk actions behind **human approval**, executes untrusted code
inside a **pluggable sandbox**, and writes a **tamper-evident audit trail** for every step.

> **Status:** v0.2 — installable package, wired agent loop, enforced RBAC, async API.
> The default sandbox provides real process-level isolation; hardware-level
> (Firecracker microVM) isolation is a pluggable backend you enable on a KVM host
> (see [Sandboxing](#-sandboxing-honest-isolation)).

---

## ✨ What EuroClaw actually does (v0.2)

| Capability | Status |
|---|---|
| Installable Python package (`pip install -e .`) | ✅ |
| Wired reason → act → observe loop that **really executes tools** | ✅ |
| RBAC enforced on every tool call (SSO-role → capability) | ✅ |
| Human-in-the-Loop approval for high-risk tools | ✅ |
| Pluggable sandbox — `subprocess` (default) or `firecracker` | ✅ / ⚙️ KVM |
| Redis-backed rate limiting, HITL & async run state (multi-replica safe) | ✅ |
| Non-blocking async run API + SSE streaming | ✅ |
| OIDC/OAuth2 auth with cached JWKS | ✅ |
| OpenTelemetry tracing (on by default) + append-only hash-chained audit log | ✅ |
| Bounded, auditable multi-agent conversations | ✅ |
| AI-assisted connector generator (`euroclaw-connectors` CLI) | ✅ |
| Local LLM inference via Ollama | ✅ |

---

## 🚀 Quickstart

```bash
# 1. Clone and install
git clone https://github.com/astream2018/euroclaw.git
cd euroclaw
python -m venv venv
source venv/bin/activate           # Windows: .\venv\Scripts\activate
pip install -e ".[dev]"

# 2. Configure
cp .env_example .env               # edit as needed

# 3. Run the tests (no external services required)
pytest tests/unit -q

# 4. Start the API
python -m euroclaw                 # serves on http://localhost:8000
#    docs at /docs, health at /healthz/liveness
```

Use it programmatically:

```python
from euroclaw import EuroclawOrchestrator

orch = EuroclawOrchestrator(name="MyAgent")
print(orch.handle_request("Summarize the latest EU AI Act guidance", roles=["analyst"]))
```

> Reasoning requires a local model. See [Local LLM inference](#-local-llm-inference).
> Without one, the gateway **fails closed** with an explicit error — it never
> fabricates an answer or a tool call.

---

## 🧠 Architecture

```
euroclaw/
├── app.py            FastAPI: async run API, SSE, RBAC-guarded endpoints, webhooks
├── orchestrator.py   Reason→act→observe loop, RBAC + HITL + dispatch, audit
├── rbac.py           Role → tool capability policy (env-overridable)
├── security.py       OIDC/OAuth2 JWT validation with cached JWKS
├── state.py          Redis-backed rate-limit / HITL / run store (+ in-mem fallback)
├── llm_gateway.py    Sovereign local inference (fails closed)
├── toolcall.py       Deterministic tool-call parser
├── multi_agent.py    Bounded, role-specialized conversation DAG
├── agent_loader.py   agents.yaml → AgentProfile
├── sandbox/          Pluggable execution: subprocess (default) | firecracker (vsock)
├── connectors/       AI-assisted connector generator + CLI (out-of-process tool)
├── plugins/          Messaging (Slack/Teams/Telegram/WhatsApp/Email), web, files, MCP
├── audit.py          Append-only, hash-chained audit ledger
└── worker.py         Celery worker for distributed execution
```

The reasoning loop is genuinely wired: the LLM emits `TOOL_CALL: <tool> | Arguments: <args>`,
the orchestrator parses it, checks RBAC, routes high-risk tools through HITL, executes in
the sandbox, feeds the observation back, and repeats up to `MAX_TOOL_ITERATIONS`.

---

## 🔐 Security & governance

- **RBAC (enforced, not decorative):** every tool call is checked against a role→capability
  policy ([`euroclaw/rbac.py`](euroclaw/rbac.py)). Roles come from the OIDC token
  (`realm_access.roles`). Override per-deployment via `RBAC_POLICY`.
- **Human-in-the-Loop:** high-risk tools (`execute_bash`, `send_external_email`, …) and MCP
  queries pause and persist an approval request; resolve it via `POST /api/v1/hitl/callback`.
- **Fail-closed inference:** the gateway raises `LLMUnavailableError` on failure — it never
  invents commands (the previous `rm -rf` "fallback" is gone).
- **Scoped MCP:** the MCP subprocess receives an explicit env allowlist, not the entire
  parent environment.
- **Audit:** every RBAC decision, HITL outcome, and tool execution is appended to a
  hash-chained JSONL ledger (`AUDIT_DIR`) and emitted as an OpenTelemetry span.

## 🧪 Sandboxing (honest isolation)

`SANDBOX_BACKEND` selects the execution boundary:

- **`subprocess`** (default): real, working isolation — temp working dir, minimized
  environment, POSIX resource limits (CPU/memory/file-size), wall-clock timeout. This is a
  **process-level** boundary, **not** a hardware/kernel boundary. Good for trusted-ish tools
  and development.
- **`firecracker`**: hardware-isolated microVM per task over `virtio-vsock`. Requires a
  **KVM-enabled Linux host** (`/dev/kvm`) plus a kernel + rootfs image and a guest agent
  listening on the vsock port. On non-KVM hosts it raises `SandboxUnavailable` telling you to
  switch backends — it does not pretend to isolate.

## 🌐 Execution modes

- **`local`**: the orchestrator executes tools in-process (dev / single node).
- **`distributed`**: tool requests are dispatched to Celery workers over Redis, each running
  the identical RBAC + HITL + sandbox path.

```bash
celery -A euroclaw.worker celery_app worker --loglevel=info --concurrency=4
```

Rate-limit, HITL, and run state live in Redis, so limits and approvals are correct across
replicas.

---

## 🔌 API (async, non-blocking)

```http
POST /api/v1/orchestrate           # returns { run_id, status } immediately
GET  /api/v1/runs/{run_id}         # poll status + result
GET  /api/v1/runs/{run_id}/events  # Server-Sent Events stream
POST /api/v1/hitl/callback         # approve/deny a paused high-risk action
GET  /healthz/liveness | /healthz/readiness
```

Add `?wait=true` to `orchestrate` for a synchronous response (handy for scripts/tests).

Multi-agent request:

```json
{
  "text": "Draft a launch plan",
  "roleplay": { "persona": "executive sponsor" },
  "conversation": {
    "participants": [
      { "name": "analyst", "role": "product strategist" },
      { "name": "reviewer", "role": "risk reviewer" }
    ]
  }
}
```

Each participant gets its own role-scoped instruction; turns are bounded by `MAX_AGENT_TURNS`.

---

## 🧩 AI-assisted connectors

Generate a new connector scaffold from a description (out-of-process; generated code is
**untrusted** and marked `.pending-review` until you approve it):

```bash
euroclaw-connectors generate --description "Fetch tickets from api.example.com" --out ./my_connector
euroclaw-connectors validate ./my_connector
```

---

## 🖼️ Visual Canvas UI

A standalone drag-and-drop orchestration canvas lives in [`ui/`](ui/) (Vite + React +
TypeScript). It talks to the core only over the REST/SSE API and holds no privilege of
its own — every action carries the user's OIDC token and is re-authorized server-side.

```bash
cd ui && npm install && npm run dev   # http://localhost:3000 (proxies to :8000)
```

## 🎓 Example: a scheduled branding agent

A runnable example lives in [`examples/brand_agent/`](examples/brand_agent/)
(`agents.yaml` + `brand_bot.py`). Load agents declaratively:

```python
from euroclaw.agent_loader import load_agents_from_yaml, get_profile
loaded = load_agents_from_yaml("examples/brand_agent/agents.yaml")
profile = get_profile(loaded, "BrandStrategist")
```

---

## 🖥️ Local LLM inference

EuroClaw runs fully offline via [Ollama](https://ollama.com):

```bash
brew install ollama        # macOS; Linux/Windows-WSL: see ollama docs
ollama serve &
ollama run mistral
```

```env
LOCAL_LLM_ENDPOINT=http://localhost:11434
EUROCLAW_MODEL=mistral
```

---

## 🚢 Deployment

- [`deploy/docker-compose.yml`](deploy/docker-compose.yml) — API + Redis
- [`docker-compose.yml`](docker-compose.yml) — full dev stack (Redis, Jaeger, Keycloak)
- [`deploy/kubernetes.yaml`](deploy/kubernetes.yaml) / [`helm/euroclaw`](helm/euroclaw) — Kubernetes
- See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) and
  [`docs/PRODUCTION_READINESS_AUDIT.md`](docs/PRODUCTION_READINESS_AUDIT.md).

The container base image (`python:3.12-slim`) may carry upstream OS CVEs; pin/patch it to
your organization's hardened base for regulated deployments.

---

## 📜 License

Apache 2.0.
