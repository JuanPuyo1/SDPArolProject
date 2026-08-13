# Architecture — Arol Customer Platform

**Audience:** Engineers joining the monorepo, agent partners, and anyone wiring frontend ↔ Django ↔ MCP ↔ orchestrator.

**Related docs:**
- [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) — business vision and monorepo sketch
- [ORCHESTRATOR_IMPLEMENTATION.md](./ORCHESTRATOR_IMPLEMENTATION.md) — Stub vs LangGraph, SSE contract, adapter checklist
- [ORCHESTRATOR_GUIDE.md](./ORCHESTRATOR_GUIDE.md) — MCP tool catalog, schemas, agent routing
- [.env.example](../.env.example) — environment variable template (copy to `.env`)

---

## 1. What this system is

Arol’s **Customer Platform** is a tenant-scoped Industry 4.0 web app:

1. Technicians sign in and see **their** machines (manuals, specs, QR-linked records).
2. They chat with a **governed AI assistant** (not a free-form LLM with DB access).
3. The assistant reaches the real world only through an **MCP tool layer**.
4. An **orchestrator** (Stub today, LangGraph in production) decides *which* tools to call and how to answer.

**Hard rules:**

- Agents and the orchestrator **never** query Django ORM / SQL directly.
- Every scoped tool call carries **`customer_id`** + **`machine_serial`** and is re-validated in MCP.
- Secrets and runtime switches live in **`.env`** (repo root), never in frontend code or git.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  frontend/   Vite + React + TypeScript                          │
│  Welcome / Login · Machine · Manual · Chatbot · Profile         │
└────────────────────────────┬────────────────────────────────────┘
                             │  session cookie + CSRF
                             │  /api/auth · /api/machines · /api/agents/chat (SSE)
┌────────────────────────────▼────────────────────────────────────┐
│  Backend/   Django 6                                          │
│                                                               │
│  authentication  →  sessions, login/logout, profile           │
│  machines        →  fleet ORM (one user → many machines)      │
│  agents          →  HTTP/SSE edge only                        │
│       │                                                       │
│       ▼  OrchestratorPort.run(...)                            │
│  StubOrchestrator  |  LangGraphOrchestrator (partner)         │
│       │                                                       │
│       ▼  registry.invoke(tool, params)                        │
│  mcp_server      →  tools + Pydantic schemas + scoping        │
│       │                                                       │
│       ▼                                                       │
│  machines / rag_engine (planned) / core (logging, costs)      │
└───────────────────────────────────────────────────────────────┘
```

| Layer | Owns | Does not own |
|-------|------|--------------|
| **Frontend** | UI, routes, SSE client | Business rules, DB, LLM keys |
| **Django views** | Auth, CSRF, machine ownership checks, SSE framing | Agent planning / tool loops |
| **Orchestrator** | Planning, routing, prompts, streaming tokens | Raw ORM, inventing parallel APIs |
| **MCP server** | Tool I/O contracts, tenant re-checks, domain adapters | Chat UX, graph topology |
| **Domain apps** (`machines`, …) | Persistence and REST for the SPA | Agent prompts |

---

## 3. Monorepo layout (runtime view)

```tree
SDPProject/
├── .env                 # Local secrets & switches (gitignored)
├── .env.example         # Safe template committed to git
├── documentation/       # Architecture + orchestrator docs
├── frontend/            # React SPA (proxy /api → Django)
└── Backend/
    ├── manage.py
    ├── requirements.txt
    ├── config/          # settings (loads ../.env), urls, wsgi/asgi
    └── apps/
        ├── authentication/
        ├── machines/
        ├── mcp_server/  # tools/, schemas/, registry.py
        ├── agents/      # views, ports, stub, langgraph adapter, factory
        ├── core/        # shared logging / cost tracking (planned use)
        └── rag_engine/  # planned — embeddings / vector search
```

---

## 4. Authentication & sessions

- Django’s **default auth + sessions** (`authenticate` / `login` / `logout`).
- SPA uses cookie sessions (`credentials: 'include'`) via Vite proxy to `127.0.0.1:8000`.
- Closing a tab keeps the user logged in until logout, cookie clear, or session expiry (~2 weeks by default).
- Chat and machine APIs require an authenticated session; **`customer_id` is never taken from the client body** — views set it from `request.user.username`.

---

## 5. Machines domain

- Model: one **User** owns many **Machine** records (serial, specs, manual URL, units, certifications, …).
- Frontend **Machine** and **Manual** pages load from `GET /api/machines/default/` (or by serial).
- Demo seed: user `demo`, serial `A3279` → `python manage.py seed_demo_machine`.
- Chat resolves `machine_serial` from the body or falls back to the user’s first owned machine; invalid/unowned serials → **404**.

---

## 6. MCP server — tool gateway

**Purpose:** Every external operation (machine lookup, manual search, telemetry, tickets, …) is an MCP tool with explicit Pydantic schemas.

**How to call (orchestrators / agents):**

```python
from apps.mcp_server import registry

result = registry.invoke(
    "get_machine_info",
    {"customer_id": "demo", "machine_serial": "A3279"},
)
# {"status": "ok", "data": {...}}  or  {"status": "error", "message": "...", "code": "..."}
```

**Expectations:**

| Ready today (Vector DB & ORM) | Stub contract (stable I/O, placeholder data) |
|--------------------------------|---------------------------------------------|
| `echo`, `get_machine_info`, `list_customer_machines`, `search_manual` (Qdrant) | `query_telemetry`, `list_spare_parts`, `create_ticket` |

Full catalog and schemas: [ORCHESTRATOR_GUIDE.md](./ORCHESTRATOR_GUIDE.md).

Local debug HTTP (`DEBUG` only): `GET /api/mcp/tools/`, `POST /api/mcp/tools/<name>/invoke/`. Production agents must use **in-process** `registry.invoke`.

---

## 7. Orchestrator — what to expect

The orchestrator is the **brain behind chat**. Django only selects a backend and streams chunks.

### Common contract (`OrchestratorPort`)

```text
run(customer_id, machine_serial, message, attachments?) → Iterator[OrchestratorChunk]
```

Chunk types the frontend already understands:

| Type | Meaning |
|------|---------|
| `token` | Streamed assistant text |
| `tool` | MCP tool name + invoke envelope |
| `step` | Thinking or execution step indicator |
| `error` | Error message for the UI |
| `done` | End of run |

HTTP: `POST /api/agents/chat/` → `text/event-stream`. Details: [ORCHESTRATOR_IMPLEMENTATION.md](./ORCHESTRATOR_IMPLEMENTATION.md).

### Backends

| Backend | Env value | Status | What you get |
|---------|-----------|--------|--------------|
| **StubOrchestrator** | `ORCHESTRATOR_BACKEND=stub` | Implemented | TroubleshootingServiceAgent chains; calls real MCP tools (including Qdrant vector search); streams Anthropic tokens if key set, else canned text |
| **LangGraphOrchestrator** | `ORCHESTRATOR_BACKEND=langgraph` | Placeholder | Partner graph: multi-step planning, agent routing, real tool loops |

**Stub does not:** multi-agent routing, LLM tool choice, conversation memory, cost accounting. Those are LangGraph / platform follow-ups.

**LangGraph must:** keep `customer_id` + `machine_serial` in state; call MCP only; map graph events to the chunk types above — no parallel SSE protocol.

---

## 8. Agents — what to expect

“Agents” are **domain specialists** selected by the orchestrator (especially under LangGraph). They are **not** separate HTTP services in this monorepo; they are logical roles that own MCP tools.

| Agent | Owner | Primary tools | Expectation |
|-------|-------|---------------|-------------|
| **Shared** | Platform | `get_machine_info`, `list_customer_machines`, `echo` | Always available to every agent |
| **Manuals** | Partner / Platform | `search_manual` | Qdrant vector retrieval for manuals (parent-child passages) |
| **Telemetry** | Partner | `query_telemetry` | Metrics / time series for a machine |
| **Business** | Partner | `list_spare_parts` | Parts catalog / upsell hints |
| **Troubleshooting** | Esteban / Platform | `search_manual` | Alarms → Qdrant vector manual search + diagnosis + recommended actions |
| **Service** | Esteban | `create_ticket` | Open field/support tickets |

### Intent → tools (orchestrator routing hint)

| User says… | Prefer |
|------------|--------|
| Alarm / error / jam | `search_manual` |
| How do I / procedure | `search_manual` |
| Temperature / cycles | `query_telemetry` |
| Spare / part / order | `list_spare_parts` |
| Technician / ticket | `create_ticket` |
| What machine is this? | `get_machine_info` |

Until LangGraph lands, the **stub agent (`TroubleshootingServiceAgent`)** implements intent classification and tool execution chains so the full stack (UI → MCP → Qdrant → SSE) stays testable.

---

## 9. End-to-end chat flow (happy path)

1. User signs in on `/` (welcome + login).
2. Opens **AI Chatbot** (session required).
3. `ChatbotPage` → `POST /api/agents/chat/` with `{ message, machine_serial? }`.
4. `agents/views.py` checks auth, resolves owned serial, sets `customer_id = username`.
5. `factory.get_orchestrator()` reads `ORCHESTRATOR_BACKEND`.
6. Orchestrator calls MCP tools (including Qdrant Vector DB queries) → streams `step` / `tool` / `token` / `done` SSE events.
7. Frontend appends tokens into the assistant bubble.

---

## 10. Environment configuration (`.env`)

Django loads the repo-root `.env` from `Backend/config/settings.py` via `python-dotenv`:

```python
load_dotenv(BASE_DIR.parent / '.env')
```

### Setup

1. Copy the template: `cp .env.example .env`
2. Fill secrets locally.
3. **Never commit `.env`** — it is listed in `.gitignore`. Commit only `.env.example`.

### Variables (current)

| Variable | Example / default | Purpose |
|----------|-------------------|---------|
| `ORCHESTRATOR_BACKEND` | `stub` | `stub` = local/CI simulator; `langgraph` = partner adapter |
| `ANTHROPIC_API_KEY` | *(empty)* | Optional. If set, StubOrchestrator streams real Claude replies; if unset, canned SSE tokens |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Model id used when the API key is present |
| `QDRANT_URL` | `:memory:` | Qdrant DB server URL (or `:memory:` for local in-memory vector DB) |
| `QDRANT_API_KEY` | *(empty)* | Optional API key for cloud or authenticated Qdrant cluster |

Template (`.env.example`):

```env
ORCHESTRATOR_BACKEND=stub
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
QDRANT_URL=:memory:
```

---

## 11. Local development checklist

```bash
# Backend (from Backend/)
cd Backend
python manage.py migrate
python manage.py seed_demo_machine --username demo
python manage.py runserver          # http://127.0.0.1:8000

# Frontend
cd frontend
npm install
npm run dev                         # http://localhost:5173  (proxies /api)
```

Demo login: `demo` / `demo1234`.

Useful tests:

```bash
python manage.py test apps.mcp_server apps.agents
```

---

## 12. What is done vs next

| Area | Today | Next |
|------|-------|------|
| Auth + sessions | Done | Customer org model beyond username if needed |
| Machines API + UI | Done (A3279 seed) | Multi-machine picker in UI |
| MCP registry + tools | Done | Wire remaining stubs (telemetry, tickets, ERP) |
| Vector DB RAG Engine | Done (Qdrant + FastEmbed) | Additional document sources & manual PDF ingestion |
| Stub orchestrator + SSE chat | Done (`TroubleshootingServiceAgent`) | — |
| LangGraph orchestrator | Adapter stub | Partner graph + agent routing |
| Cost / token logging | Planned (`core`) | Wire on every tool/LLM call |

---

## 13. Doc map (where to dig deeper)

| Question | Doc |
|----------|-----|
| Why the product exists / app list | [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) |
| How Stub/LangGraph plug in + SSE shape | [ORCHESTRATOR_IMPLEMENTATION.md](./ORCHESTRATOR_IMPLEMENTATION.md) |
| Exact tool I/O and agent ownership | [ORCHESTRATOR_GUIDE.md](./ORCHESTRATOR_GUIDE.md) |
| Coding constraints for Cursor | [../.cursorrules](../.cursorrules) |
| Env template | [../.env.example](../.env.example) |
