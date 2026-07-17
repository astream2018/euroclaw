# EuroClaw Canvas (standalone UI)

A **separate, non-core** front-end for the EuroClaw API — a visual orchestration
canvas where you drag agents onto a board, configure a facilitator persona, run
workflows, and watch execution stream live over Server-Sent Events.

It is intentionally decoupled from the core framework: it talks to EuroClaw only
over the versioned REST/SSE API and holds **no privilege of its own** — every
action carries the user's OIDC token and is re-authorized server-side.

## Stack

Vite + React + TypeScript. This is a **scaffold** (a production canvas would use a
graph library such as React Flow and persist workflows via the API).

## Develop

```bash
cd ui
npm install
npm run dev        # http://localhost:3000, proxies /api and /healthz to :8000
```

Run the EuroClaw backend separately (`python -m euroclaw`). Paste an OIDC bearer
token into the UI to authorize `orchestrate` calls.

## API surface used

| UI action | Endpoint |
|---|---|
| Health badge | `GET /healthz/readiness` |
| Run workflow | `POST /api/v1/orchestrate` |
| Live events | `GET /api/v1/runs/{id}/events` (SSE) |
| Result poll | `GET /api/v1/runs/{id}` |
| Approve/deny HITL | `POST /api/v1/hitl/callback` |

## Build

```bash
npm run build      # type-checks then bundles to dist/
```

> This project is not covered by the Python test suite or CI; wire up its own
> pipeline (or split it into its own repository) before shipping.
