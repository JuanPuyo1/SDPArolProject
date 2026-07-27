# Project Context: Arol SpA Customer Platform (Industry 4.0 AI Agent)

## 1. Project Overview & Business Vision
**Arol SpA** is a global leader in capping and packaging machinery. As part of its Industry 4.0 / 5.0 digital transformation, Arol is building a centralized **Customer Platform**.

### Primary Objectives:
1. **Interactive Machine Support & Digital Manuals**: Compliance with EU digital manual directives via QR codes placed on physical machines. Instant access to vectorized user manuals, error codes, and maintenance instructions.
2. **Controlled Agentic AI Architecture**: Replace unstructured LLM chats with **governed, deterministic AI Agents** driven by a **LangGraph** orchestrator and interacting through an **MCP (Model Context Protocol) Server**.
3. **Upselling & Service Integration**: Proactively guide technicians and plant managers toward spare parts ordering, scheduled maintenance, and field support ticketing.
4. **Data Isolation & Cost Governance**: Enforce strict tenant isolation (customers only see their assigned machines) and track token usage/costs across agent calls.

---

## 2. Monorepo Repository Structure

```tree
SDPProject/
├── PROJECT_CONTEXT.md
├── .cursorrules
├── .venv/                        # Python virtualenv (repo root)
├── frontend/                     # React SPA — layout and stack may evolve
│   ├── components/               # Page-level UI (Machine, Manual, Chatbot, NavBar)
│   ├── src/
│   │   ├── data/                 # Static fixtures today; replace with API hooks later
│   │   ├── hooks/                # API clients & SSE streaming (to be added)
│   │   ├── App.tsx               # React Router routes
│   │   └── main.tsx
│   ├── public/                   # Static assets (manual PDFs, images)
│   └── package.json              # Vite + React + TypeScript
└── backend/                      # Django backend & MCP Engine
    ├── manage.py
    ├── requirements.txt
    ├── config/                   # Django settings, URLs, WSGI/ASGI
    └── apps/
        ├── core/                 # Shared utilities, logging & cost tracking (Django app)
        ├── authentication/       # User/Customer permissions & session scoping (Django app)
        ├── machines/             # (planned) Machine models, QR mapping, telemetry
        ├── rag_engine/           # (planned) pgvector, embeddings, vector search
        ├── mcp_server/           # Django app boundary; tool logic is plain Python
        └── agents/               # Django chat API + OrchestratorPort (LangGraph / stub)
```

---

## 3. End-to-End Request Flow

```
Frontend ChatbotPage
    ↓  POST / SSE  { customer_id, machine_serial, message }
Django apps/agents/views.py          ← HTTP / auth / SSE only
    ↓  OrchestratorPort.run(...)
LangGraph graph (production)         ← partner-owned planner & tool loop
  — or —
StubOrchestrator (local / CI)        ← same port; rule-based / canned replies
    ↓  tool nodes call MCP tools only
apps/mcp_server (tools + schemas)
    ↓
machines / rag_engine / authentication / core
```

One customer owns many machines. Every orchestrator run and every MCP tool call must carry and re-validate `customer_id` + `machine_serial`.

---

## 4. Architecture Layers

### Frontend (`frontend/`)
- **Current stack**: Vite, React 19, TypeScript, React Router, plain CSS.
- **Role**: Pure client. Renders machine info, manual viewer, and chat UI. No business logic or direct DB access.
- **Evolution**: The frontend may be refactored as the Django API is wired up. Prefer incremental changes unless a broader redesign is requested.
- **Backend integration**: Chat streams from `apps/agents/` (SSE). Machine/manual lists from `machines` / `rag_engine` APIs when available.

### Backend Django apps

| App | Type | Responsibility |
|-----|------|----------------|
| `core` | Django-heavy | Shared utils, structured logging, token/cost tracking |
| `authentication` | Django-heavy | Users, customers, tenant scoping, permissions |
| `machines` | Django-heavy | ORM models, customer → many machines, QR mapping, telemetry stubs |
| `rag_engine` | Django-heavy | pgvector storage, embeddings, retrieval |
| `mcp_server` | **Boundary app** | MCP tool definitions & execution; plain Python tools/schemas |
| `agents` | **Boundary app** | Chat HTTP/SSE; **OrchestratorPort** → LangGraph or Stub |

### `mcp_server` — tool layer

```tree
apps/mcp_server/
├── tools/           # search_manual, get_machine, list_customer_machines, create_ticket, …
├── schemas/         # Pydantic input/output models per tool
├── registry.py      # Tool registration & discovery
├── views.py         # Optional HTTP handlers
└── urls.py
```

- Tools may use Django ORM in other apps; agents and LangGraph nodes must **not**.
- Structured errors: `{"status": "error", "message": "..."}`.

### `agents` — LangGraph orchestrator (production) + stub (dev)

Django owns the HTTP boundary. **LangGraph** owns planning, routing, and the tool-execution loop. A shared **OrchestratorPort** lets local/dev run without the full graph.

```tree
apps/agents/
├── views.py                    # POST /chat, SSE stream to frontend
├── ports.py                    # OrchestratorPort protocol
├── stub_orchestrator.py        # Dev/CI simulator (same interface)
├── langgraph_orchestrator.py   # Thin adapter to partner LangGraph graph
├── graphs/                     # Optional: partner graph package (or external dep)
├── prompts/                    # Shared / partner prompts as needed
└── urls.py
```

**OrchestratorPort (conceptual):**
```python
async def run(
    *,
    customer_id: str,
    machine_serial: str,
    message: str,
    attachments: list | None = None,
) -> AsyncIterator[str]:  # SSE / token chunks
    ...
```

| Backend | When | Behavior |
|---------|------|----------|
| `StubOrchestrator` | Local / CI (`ORCHESTRATOR_BACKEND=stub`) | Canned or rule-based replies; may call 1–2 real MCP tools to exercise the stack; streams fake tokens over SSE |
| `LangGraphOrchestrator` | Integration / prod (`ORCHESTRATOR_BACKEND=langgraph`) | Runs partner LangGraph graph; tool nodes call `mcp_server` only; streams graph events → SSE |

- Views **never** import LangGraph nodes directly — only the port factory.
- LangGraph tool nodes are adapters around MCP tools (same Pydantic schemas); **no raw SQL / ORM** inside the graph.
- Partner may ship the graph inside `apps/agents/graphs/` or as a separate installable package; the adapter hides that choice.

---

## 5. Multi-machine ownership

- `authentication`: identity and customer tenancy.
- `machines`: one customer → many machines (`serial_number`, model, QR token, FK to customer).
- Chat and MCP tools are always scoped to the active `machine_serial` for that `customer_id`.
- Frontend should eventually list the user’s fleet, then open chat in machine context (QR or selection).

---

## 6. Data & Assets
- `Data/` — source manuals (PDF) and telemetry CSVs for RAG ingestion and `machines` seeding.
- Frontend `public/manual/` — PDF for the manual viewer until API-backed delivery exists.

---

## 7. Local Development

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev          # http://localhost:5173
```

**Backend** (from repo root, with `.venv` active):
```bash
cd backend
# default for local: stub orchestrator
set ORCHESTRATOR_BACKEND=stub
python manage.py runserver   # http://127.0.0.1:8000
```

To exercise the partner graph when available:
```bash
set ORCHESTRATOR_BACKEND=langgraph
python manage.py runserver
```

Requires **Node ≥ 22.12** for Vite 8. Python **3.13** with Django **6.x** in `.venv`.
