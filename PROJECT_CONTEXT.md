# Project Context: Arol SpA Customer Platform (Industry 4.0 AI Agent)

## 1. Project Overview & Business Vision
**Arol SpA** is a global leader in capping and packaging machinery. As part of its Industry 4.0 / 5.0 digital transformation, Arol is building a centralized **Customer Platform**.

### Primary Objectives:
1. **Interactive Machine Support & Digital Manuals**: Compliance with EU digital manual directives via QR codes placed on physical machines. Instant access to vectorized user manuals, error codes, and maintenance instructions.
2. **Controlled Agentic AI Architecture**: Replace unstructured LLM chats with **governed, deterministic AI Agents** interacting through an **MCP (Model Context Protocol) Server**.
3. **Upselling & Service Integration**: Proactively guide technicians and plant managers toward spare parts ordering, scheduled maintenance, and field support ticketing.
4. **Data Isolation & Cost Governance**: Enforce strict tenant isolation (customers only see their assigned machines) and track token usage/costs across agent calls.

---

## 2. Monorepo Repository Structure
The repository is split into clean `frontend/` and `backend/` directories:

```tree
arol-customer-platform/
├── PROJECT_CONTEXT.md
├── .cursorrules
├── frontend/                     # React SPA (Vite + React Router + CSS)
│   ├── components/               # UI Components (Chat Interface, Manuals, Machine Info)
│   ├── src/
│   │   ├── data/                 # Static / API-backed domain data
│   │   ├── hooks/                # React Hooks for API & SSE streaming (planned)
│   │   ├── App.tsx               # Route definitions (Machine, Manual, Chatbot)
│   │   └── main.tsx
│   └── package.json
└── backend/                      # Django backend & MCP Engine
    ├── manage.py
    ├── config/                   # Django settings, URLs, WSGI/ASGI
    ├── apps/
    │   ├── core/                 # Shared utilities, logging & cost tracking
    │   ├── authentication/       # User/Customer permissions & session scoping
    │   ├── machines/             # Machine models, QR code mapping, telemetry stubs
    │   ├── rag_engine/           # Pgvector / Vector DB setup & embeddings
    │   ├── mcp_server/           # MCP Server protocols, tools, and endpoints
    │   └── agents/               # Troubleshooting Agent & Orchestrator logic
    └── requirements.txt