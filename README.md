# SDPArolProject — Arol SpA Customer Platform

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Django 6.0](https://img.shields.io/badge/django-6.0-green.svg)](https://www.djangoproject.com/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![Vite 8](https://img.shields.io/badge/vite-8-646cff.svg)](https://vitejs.dev/)
[![Qdrant](https://img.shields.io/badge/Qdrant-VectorDB-red.svg)](https://qdrant.tech/)

An **Industry 4.0 / 5.0 AI Agent & Customer Platform** for **Arol SpA** (global leader in capping and packaging machinery).

This platform provides machine operators, plant managers, and field service engineers with interactive digital manual access, vector-search-powered troubleshooting, telemetry inspection, and support ticket escalation through a governed AI agent architecture.

---

## 🌟 Key Features

- **Governed Agentic AI Architecture**: Clean separation between Django HTTP edge, orchestrator planning, and an **MCP (Model Context Protocol)** tool gateway.
- **RAG Vector Search Engine**: Integrated **Qdrant Vector Database** using **FastEmbed** embeddings for semantic retrieval over machine manuals and troubleshooting error codes.
- **Tenant-Scoped Access**: Strict tenant isolation guaranteeing that queries and tools execute only against machines owned by the authenticated customer.
- **SSE Streaming UI**: Real-time reasoning steps, tool invocation indicators, and token-by-token streaming response display in React.
- **Flexible Orchestrator Backend**: Switch seamlessly between a local development simulator (`StubOrchestrator`) and production partner graph (`LangGraphOrchestrator`).

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  frontend/   Vite 8 + React 19 + TypeScript                     │
│  Welcome / Login · Machine · Manual · Chatbot · Profile         │
└────────────────────────────┬────────────────────────────────────┘
                             │  Session Cookie + CSRF
                             │  /api/auth · /api/machines · /api/agents/chat (SSE)
┌────────────────────────────▼────────────────────────────────────┐
│  Backend/   Django 6                                            │
│                                                                 │
│  authentication  →  Session auth, login/logout, user profile    │
│  machines        →  Fleet ORM (customer → machine mapping)      │
│  agents          →  HTTP/SSE boundary & OrchestratorPort        │
│       │                                                         │
│       ▼  OrchestratorPort.run(...)                              │
│  StubOrchestrator  |  LangGraphOrchestrator (production graph)  │
│       │                                                         │
│       ▼  registry.invoke(tool, params)                          │
│  mcp_server      →  Tools, Pydantic schemas & tenant scoping    │
│       │                                                         │
│       ├── rag_engine  →  Qdrant Vector DB + FastEmbed search    │
│       └── machines / core / authentication                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```tree
SDPArolProject/
├── README.md                           # Project root documentation
├── PROJECT_CONTEXT.md                  # Business vision, domain context & codebase guide
├── .env.example                        # Environment variable template
├── documentation/                      # Architecture & orchestrator guides
│   ├── ARCHITECTURE.md                 # Technical architecture reference
│   ├── ORCHESTRATOR_GUIDE.md           # MCP tool catalog & agent specifications
│   └── ORCHESTRATOR_IMPLEMENTATION.md  # Port contract, SSE framing & adapter guide
├── frontend/                           # React 19 + TypeScript + Vite SPA
│   ├── components/                     # Page components (ChatbotPage, MachinePage, etc.)
│   ├── src/
│   │   ├── api/                        # API clients & SSE chat stream reader
│   │   ├── hooks/                      # Custom hooks (useChat)
│   │   └── App.tsx                     # Main routes
│   └── vite.config.ts                  # Vite config with /api dev proxy
└── Backend/                            # Django backend & MCP engine
    ├── manage.py
    ├── config/                         # Settings, URLs, WSGI/ASGI
    └── apps/
        ├── authentication/             # User sessions & login management
        ├── machines/                   # Fleet ORM models & demo seeders
        ├── mcp_server/                 # MCP tool registry, tools & rag_engine
        │   ├── rag_engine/             # Qdrant client, collections & search
        │   └── tools/                  # search_manual, search_error_codes, etc.
        ├── agents/                     # HTTP/SSE endpoints, ports & orchestrators
        └── core/                       # Shared logging & cost utilities
```

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python 3.13+**
- **Node.js ≥ 22.12** (required for Vite 8)

### 1. Environment Setup

Clone the repository and set up environment variables:

```bash
cp .env.example .env
```

Default `.env` configuration:
```env
ORCHESTRATOR_BACKEND=stub
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
QDRANT_URL=:memory:
```

### 2. Backend Setup

From the repository root, activate your virtual environment and navigate to `Backend/`:

```bash
cd Backend
python manage.py migrate
python manage.py seed_demo_machine --username demo --password demo1234
python manage.py runserver
```

The Django API server will start at `http://127.0.0.1:8000`.

### 3. Frontend Setup

In a separate terminal, navigate to `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Log in using `demo` / `demo1234`.

---

## 🛠 Important Management Commands

Below are key Django management commands available for database setup, demo data seeding, and RAG Vector DB manual ingestion:

| Command | Description |
| :--- | :--- |
| `python manage.py migrate` | Apply database migrations for auth, machines, and sessions. |
| `python manage.py seed_demo_machine --username demo` | Seed customer-owned machine record (`A3279`) and units for demo user. |
| `python manage.py ingest_markdown_manuals` | **Ingest extracted Markdown manuals (`Data/Manuals_md`) into Qdrant DB** with parent/child chunking & page markers. |
| `python manage.py seed_demo_manuals` | Seed default demo manual passages and error code entries into Qdrant DB. |
| `python manage.py ingest_manual --pdf <path> --model <model>` | Ingest a single PDF manual directly into Qdrant. |

### Running Markdown Manual Ingestion (`ingest_markdown_manuals`)

The `ingest_markdown_manuals` command parses Markdown manuals, preserves `<!-- Page N -->` page numbers and header structures, embeds chunks with FastEmbed (`bge-small-en-v1.5`), and upserts them into the Qdrant DB `arol_manuals_fastembed` collection.

```bash
# Navigate to Backend directory
cd Backend

# Ingest all markdown manuals from Data/Manuals_md into Qdrant (clears collection by default)
python manage.py ingest_markdown_manuals

# Ingest without clearing existing Qdrant points
python manage.py ingest_markdown_manuals --no-clear

# Ingest from a custom markdown directory
python manage.py ingest_markdown_manuals --dir /path/to/markdown_dir
```

---

## 🧪 Testing & Verification

### Running Unit Tests

To run tests for the MCP server tools, RAG engine, and agent endpoints:

```bash
cd Backend
python manage.py test apps.mcp_server apps.agents
```

### Testing the SSE Chat Stream via HTTP

You can test the chat endpoint directly using `curl`:

```bash
curl -N -X POST http://127.0.0.1:8000/api/agents/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Alarm E042 star-wheel jam", "machine_serial": "A3279"}'
```

---

## 📚 Documentation Map

- 📖 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — Business vision, domain context & codebase guide
- 🏗 [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) — Detailed technical architecture
- 🛠 [documentation/ORCHESTRATOR_GUIDE.md](documentation/ORCHESTRATOR_GUIDE.md) — Tool schemas & agent mapping
- ⚡ [documentation/ORCHESTRATOR_IMPLEMENTATION.md](documentation/ORCHESTRATOR_IMPLEMENTATION.md) — Orchestrator integration & SSE contract
