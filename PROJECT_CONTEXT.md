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
├── PROJECT_CONTEXT.md            # Business vision & domain context
├── README.md                     # Root project guide & quickstart
├── .cursorrules
├── .env.example                  # Safe env variable template
├── documentation/                # Architecture & orchestrator documentation
│   ├── ARCHITECTURE.md
│   ├── ORCHESTRATOR_GUIDE.md
│   └── ORCHESTRATOR_IMPLEMENTATION.md
├── frontend/                     # React 19 SPA — layout, components & SSE client
│   ├── components/               # Page-level UI (Machine, Manual, Chatbot, NavBar)
│   ├── src/
│   │   ├── api/                  # API client & SSE stream processor
│   │   ├── hooks/                # React hooks (useChat)
│   │   ├── App.tsx               # React Router routes
│   │   └── main.tsx
│   ├── public/                   # Static assets (manual PDFs, images)
│   └── package.json              # Vite 8 + React 19 + TypeScript
└── Backend/                      # Django backend & MCP Engine
    ├── manage.py
    ├── config/                   # Django settings, URLs, WSGI/ASGI
    └── apps/
        ├── core/                 # Shared utilities, logging & cost tracking
        ├── authentication/       # User/Customer permissions & session scoping
        ├── machines/             # Machine models, QR mapping, demo seeders
        ├── mcp_server/           # MCP tool gateway & registry
        │   ├── rag_engine/       # Qdrant Vector DB, FastEmbed search & ingestion
        │   ├── schemas/          # Pydantic schemas per tool
        │   └── tools/            # search_manual, get_machine_info, etc.
        └── agents/               # Django chat API + OrchestratorPort (Stub / LangGraph)
```

---

## 3. End-to-End Request Flow

```
Frontend ChatbotPage
    ↓  POST / SSE  { machine_serial, message }
Django apps/agents/views.py          ← HTTP / auth / SSE edge
    ↓  OrchestratorPort.run(...)
LangGraph graph (production)         ← partner-owned planner & tool loop
  — or —
StubOrchestrator (local / CI)        ← same port; rule-based / canned replies
    ↓  tool nodes call MCP tools only
apps/mcp_server (tools + schemas)
    ↓
rag_engine (Qdrant Vector DB) / machines / authentication / core
```

One customer owns many machines. Every orchestrator run and every MCP tool call must carry and re-validate `customer_id` + `machine_serial`.

---

## 4. Architecture Layers

### Frontend (`frontend/`)
- **Current stack**: Vite 8, React 19, TypeScript, React Router, plain CSS.
- **Role**: Pure client. Renders machine info, manual viewer, and chat UI. No business logic or direct DB access.
- **Backend integration**: Chat streams from `apps/agents/` (SSE). Machine and auth endpoints proxied via Vite dev server (`/api` -> `http://127.0.0.1:8000`).

### Backend Django apps

| App | Type | Responsibility |
|-----|------|----------------|
| `core` | Django-heavy | Shared utils, structured logging, token/cost tracking |
| `authentication` | Django-heavy | Users, customers, tenant scoping, sessions |
| `machines` | Django-heavy | ORM models, customer → many machines, QR mapping, telemetry stubs |
| `rag_engine` (in `mcp_server`) | Python + Qdrant | Vector DB client, FastEmbed embeddings, parent-child chunk retrieval |
| `mcp_server` | **Boundary app** | MCP tool definitions & execution; plain Python tools/schemas |
| `agents` | **Boundary app** | Chat HTTP/SSE edge; **OrchestratorPort** → LangGraph or Stub |

### `mcp_server` — tool layer

```tree
apps/mcp_server/
├── tools/           # search_manual, get_machine_info, create_ticket, …
├── schemas/         # Pydantic input/output models per tool
├── rag_engine/      # Qdrant client, FastEmbed embeddings, collections & vector search
├── registry.py      # Tool registration & discovery
├── scoping.py       # Ownership verification helpers
├── views.py         # Optional HTTP debug handlers
└── urls.py
```

- Tools may use Django ORM or `rag_engine`; agents and LangGraph nodes must **not** query DBs directly.
- Structured response format: `{"status": "ok", "data": {...}}` or `{"status": "error", "message": "..."}`.

### `agents` — LangGraph orchestrator (production) + stub (dev)

Django owns the HTTP boundary. **LangGraph** owns planning, routing, and the tool-execution loop. A shared **OrchestratorPort** lets local/dev run without the full graph.

```tree
apps/agents/
├── views.py                          # POST /chat, SSE stream to frontend
├── ports.py                          # OrchestratorPort protocol & chunks
├── stub_orchestrator.py              # Dev/CI simulator (same interface)
├── troubleshooting_service_agent.py  # Intent-driven dev agent with tool chains
├── langgraph_orchestrator.py         # Thin adapter to partner LangGraph graph
├── factory.py                        # Backend selector based on ORCHESTRATOR_BACKEND
└── urls.py
```

**OrchestratorPort (conceptual):**
```python
def run(
    *,
    customer_id: str,
    machine_serial: str,
    message: str,
    attachments: list | None = None,
) -> Iterator[OrchestratorChunk]:  # SSE / token chunks
    ...
```

| Backend | When | Behavior |
|---------|------|----------|
| `StubOrchestrator` | Local / CI (`ORCHESTRATOR_BACKEND=stub`) | Troubleshooting & service agent chains; calls real MCP tools (including Qdrant vector search); streams tokens over SSE |
| `LangGraphOrchestrator` | Integration / prod (`ORCHESTRATOR_BACKEND=langgraph`) | Runs partner LangGraph graph; tool nodes call `mcp_server` only; streams graph events → SSE |

- Views **never** import LangGraph nodes directly — only the port factory.
- LangGraph tool nodes are adapters around MCP tools (same Pydantic schemas); **no raw SQL / ORM** inside the graph.

---

## 5. Multi-machine ownership

- `authentication`: identity and customer tenancy.
- `machines`: one customer → many machines (`serial_number`, model, QR token, FK to customer).
- Chat and MCP tools are always scoped to the active `machine_serial` for that `customer_id`.

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

**Backend** (from `Backend/`, with `.venv` active):
```bash
cd Backend
# default for local: stub orchestrator
export ORCHESTRATOR_BACKEND=stub   # or set ORCHESTRATOR_BACKEND=stub on Windows
python manage.py runserver         # http://127.0.0.1:8000
```

To exercise the partner graph when available:
```bash
export ORCHESTRATOR_BACKEND=langgraph
python manage.py runserver
```

Requires **Node ≥ 22.12** for Vite 8. Python **3.13** with Django **6.x** in `.venv`.

--
## 7.1 update db

install Dbeaver 
create a new connection
Host: localhost
Port: 5432
Database: postgres
Username: postgres
Password: the password you set when installing PostgreSQL

then sql new script

Run only this first:
CREATE USER arol WITH PASSWORD 'arol';

Then run only this line by itself (highlight it → Ctrl+Enter):
CREATE DATABASE arol OWNER arol;

Then run:
GRANT ALL PRIVILEGES ON DATABASE arol TO arol;


## 7.2

Cd Backend
Remove-Item db.sqlite3 -ErrorAction SilentlyContinue
python manage.py migrate
py initiliaze_database.py

---

## 8. Qdrant RAG Vector DB Engine

The RAG (Retrieval-Augmented Generation) layer powers semantic search for manuals.

Location: `Backend/apps/mcp_server/rag_engine/`

Key components:
- `client.py`: Process-wide `QdrantClient` singleton supporting server URL configuration (`QDRANT_URL`) with fallback to `:memory:` for local dev and tests.
- `embeddings.py`: FastEmbed dense query embedding generator.
- `collections.py`: Manages the `manuals` Qdrant collection (`arol_manuals_fastembed`).
- `search.py`: Vector search with `machine_model` filter enforcement (tenant boundary protection) and parent-content retrieval.
- `ingest.py`: PDF/CSV/Markdown parser with parent/child text chunking pipeline.

### Manual Ingestion Command (`ingest_markdown_manuals`)

Extracted Markdown manuals (stored in `Data/Manuals_md/`) are ingested into Qdrant using the Django management command:

```bash
cd Backend
python manage.py ingest_markdown_manuals
```

Options:
- `--dir <path>`: Directory containing extracted Markdown manuals (defaults to `Data/Manuals_md`).
- `--no-clear`: Ingest without clearing the existing `arol_manuals_fastembed` Qdrant collection.

---

## 9. Key Files to Understand First

1. **[Backend/apps/agents/views.py](file:///home/fvelilla/sdp_project/repo/SDPArolProject/Backend/apps/agents/views.py)** — Chat HTTP API edge, session authentication, machine resolution, and SSE framing.
2. **[Backend/apps/agents/troubleshooting_service_agent.py](file:///home/fvelilla/sdp_project/repo/SDPArolProject/Backend/apps/agents/troubleshooting_service_agent.py)** — Intent classification (`troubleshooting`, `service`, `general`), agent reasoning, and MCP tool execution chains.
3. **[Backend/apps/mcp_server/registry.py](file:///home/fvelilla/sdp_project/repo/SDPArolProject/Backend/apps/mcp_server/registry.py)** — MCP tool specs, Pydantic schema validation, and tool invocation dispatch.
4. **[Backend/apps/mcp_server/rag_engine/search.py](file:///home/fvelilla/sdp_project/repo/SDPArolProject/Backend/apps/mcp_server/rag_engine/search.py)** — Vector retrieval over Qdrant collections with model filtering.
5. **[frontend/src/api/chat.ts](file:///home/fvelilla/sdp_project/repo/SDPArolProject/frontend/src/api/chat.ts)** — Frontend reader for streaming Server-Sent Events (SSE).
6. **[frontend/src/hooks/useChat.ts](file:///home/fvelilla/sdp_project/repo/SDPArolProject/frontend/src/hooks/useChat.ts)** — React hook processing streaming chunks (`step`, `tool`, `token`, `done`).

---

## 10. SSE Stream Inspection

The chat API streams real-time events. Inspect directly via `curl`:

```bash
curl -N -X POST http://127.0.0.1:8000/api/agents/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Alarm E042 star-wheel jam", "machine_serial": "A3279"}'
```

Stream event types:
- `step`: Agent reasoning or execution step indicator
- `tool`: Invoked MCP tool envelope (`status`, `data` or `message`)
- `token`: Assistant output text stream
- `done`: Turn execution complete
- `error`: Execution error notification

---

## 11. System Mental Model

- **Frontend**: The face of the assistant (React 19 SPA, chat stream UI).
- **Backend Edge**: The brain & controller (Django 6 HTTP, sessions, OrchestratorPort).
- **MCP Server**: The hands & tools (Pydantic schemas, scoped tool functions).
- **RAG Engine**: The memory (Qdrant Vector DB, FastEmbed embeddings).

