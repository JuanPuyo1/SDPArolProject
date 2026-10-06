# SDPArolProject — AROL Intelligent Assistant Platform

### Project Members
- **Esteban Puyo**
- **Felipe Rojas**
- **Fernando Velilla**

---

## Project Overview

The **AROL Intelligent Assistant Platform** is an Industry 4.0 multi-agent conversational system designed to assist plant operators, maintenance technicians, and managers working with AROL capping and packaging machinery.

> [!NOTE]
> For the complete slide deck summarizing the project motivation, architecture diagrams, multi-agent workflows, and benchmarking results, see the **[AROL Project Presentation (PDF)](documentation/AROL%20Project%20Presentation_Update.pdf)**. Additional architectural deep dives are available in the [`documentation/`](documentation/) directory.

Instead of treating LLMs as free-form chatbots with unrestricted database access, the system introduces a **governed, multi-agent architecture** capable of reasoning across heterogeneous, tenant-isolated industrial data streams:
- **Technical Documentation & Manuals:** Machine operational procedures, safety guidelines, lubrication schedules, and component specifications.
- **Machine Telemetry:** Real-time and historical sensor readings, operating temperatures, energy consumption (kWh), production rates (bph), and uptime percentages.
- **Alarm History:** Machine fault logs, severity classifications, and timestamped events.
- **Maintenance Records:** Work orders, preventative maintenance schedules, and field support service tickets.
- **Commercial & Contractual Data:** Machine quotes, revision histories, pricing line items, and order fulfillment tracking.

---

## System Architecture

The platform enforces strict security, privacy, and architectural boundaries across all layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend Client (React 19 + TypeScript + Vite 8)                       │
│  - QR Scanner & Deep-Linking (/m/<machineId>)                           │
│  - Multi-Chat Interface (up to 3 concurrent sessions)                   │
│  - Role-Adaptive UI (Technician vs. Commercial views)                   │
│  - Real-time Server-Sent Events (SSE) Streaming with Agent Attribution  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Session Cookie + CSRF
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Web Gateway & Backend Infrastructure (Django 6 / ASGI Uvicorn)        │
│  - Role-Based Access Control (RBAC: full, technician, commercial)       │
│  - Multi-Tenant Isolation & Fleet Ownership Enforcement                 │
│  - Server-Sent Events (SSE) Chat Gateway                                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Orchestrator Port Factory
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Multi-Agent Orchestrator (LangGraph)                                   │
│  - Intent Router & History Coordinator                                  │
│  - Thread Checkpointing (MemorySaver per conversation)                  │
│  - Specialized Agents:                                                  │
│    • Manuals Agent       • Telemetry Agent                              │
│    • Troubleshooting/Service Agent   • Orders/Business Agent            │
│  - Synthesizer (Merges multi-agent outputs; bypassed for single-agent)  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Unified Tool Protocol (registry.invoke)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Model Context Protocol (MCP) Server                                    │
│  [1. Resolve & Validate Schema] ──► [2. Authorize User Role]           │
│  [3. Authorize Machine Ownership] ──► [4. Execute & Clean Envelope]     │
└──────────────────┬─────────────────────────────────┬────────────────────┘
                   │                                 │
                   ▼                                 ▼
┌───────────────────────────────────┐ ┌───────────────────────────────────┐
│  PostgreSQL 16 (Operational DB)   │ │  Qdrant Vector DB + FastEmbed     │
│  Telemetry, Alarms, Tickets,      │ │  Hybrid RAG Engine (384-dim,      │
│  Quotes, Orders, Fleet Metadata   │ │  PyMuPDF + Parent-Child Chunks)   │
└───────────────────────────────────┘ └───────────────────────────────────┘
```

### Key Components

1. **Frontend Client (`frontend/`)**: Built with React 19, Vite 8, and TypeScript. Includes QR-code machine scanning for instantaneous machine context locking (`/m/:machineId`), concurrent multi-session chat interfaces (up to 3 simultaneous machine chats), an embedded PDF/Markdown manual viewer, and real-time SSE streaming with visual agent attribution indicators.
2. **Backend & Gateway (`Backend/`)**: Built on Django 6 served asynchronously via Uvicorn. Manages user authentication, session persistence, tenant isolation, and fleet RBAC (restricting technicians and commercial users to permitted data scopes).
3. **LangGraph Multi-Agent Orchestrator**:
   - **Router:** Parses the incoming user query and conversation context to route tasks to one or more specialist agents.
   - **Manuals Agent:** Performs semantic search across machine documentation and manuals (`search_manual`).
   - **Telemetry Agent:** Queries and aggregates sensor metrics, production rates, uptime, and energy consumption (`query_telemetry`).
   - **Troubleshooting Agent:** Diagnoses machine faults, searches alarm codes, and views or generates maintenance tickets (`list_alarms`, `search_error_codes`, `list_maintenance_tickets`, `create_ticket`).
   - **Orders & Business Agent:** Retrieves quotation histories, revision changes, and order fulfillment states (`get_quote_history`, `get_order_status`).
   - **Synthesizer:** Merges cross-agent answers into a single coherent response. When only a single specialist is required, the merge step is bypassed to reduce token consumption and latency.
4. **Governed Model Context Protocol (MCP) Server**: A unified tool execution boundary enforcing a 4-step pipeline:
   - *Resolve & Validate:* Validates input schemas using strict Pydantic definitions (`VALIDATION_ERROR`).
   - *Role Authorization:* Verifies caller permissions against role policies (`FORBIDDEN`).
   - *Ownership Verification:* Ensures the user's company owns the requested machine (`FORBIDDEN`/`NOT_FOUND`).
   - *Execution Envelope:* Returns structured responses `{ "status": "ok", "data": ... }`. Agents never interact with the database directly, eliminating data leakage and hallucinations.
5. **Vector Database & RAG Pipeline**:
   - **Qdrant Vector DB:** Cloud cluster or local container deployment.
   - **FastEmbed:** Local ONNX embedding execution using `BAAI/bge-small-en-v1.5` (384-dimensional dense vectors, cosine distance).
   - **Document Pipeline:** PyMuPDF converts PDF manuals to Markdown (0.1–0.5s/page) with parent-child recursive text chunking tagged with serial numbers and chapter/section metadata.
6. **Observability (LangSmith)**: Integrated tracing of routing decisions, multi-agent execution graphs, latency waterfalls, token usage, and cost tracking.

---

## Benchmarking & Quantitative Results

The system was evaluated using **13 standardized benchmark tests** spanning single-domain inquiries (manuals, quotes, orders, telemetry, alarms, tickets) and complex cross-agent tasks (e.g., Alarms + Manuals, Maintenance Tickets + Manuals, Orders + Quotes).

Responses were scored using standard evaluation criteria:
- **Successful (Score: 5.0):** Model selects the correct data sources, invokes appropriate tools, and answers the query completely and accurately.
- **Mid-successful (Score: 2.5):** Model retrieves relevant data but provides an incomplete clarification or omits secondary details.
- **Failure (Score: 0.0):** Model fails to retrieve the correct data, hallucinates, or cannot answer the question.

### Overall Performance Comparison

| Metric | Cloud API: Anthropic (`claude-haiku-4-5-20251001`) | Local Edge LLM: Ollama (`qwen2.5:3b`) |
| :---------------------------------------- | :------------------------------------------------ | :------------------------------------ |
| **Overall Score (0 to 5 scale)**          | **4.81 / 5.0**                                    | **3.65 / 5.0**                        |
| **Success Rate**                          | **92%** (12 / 13 Successful)                      | **54%** (7 / 13 Successful)           |
| **Mid-Successful Rate**                   | **8%** (1 / 13 Mid-successful)                    | **38%** (5 / 13 Mid-successful)       |
| **Failure Rate**                          | **0%** (0 Failures)                               | **8%** (1 / 13 Failure)               |
| **Mean Response Latency**                 | **7.47 s**                                        | **12.97 s**                           |
| **Mean Tokens per Query**                 | **10,192 tokens**                                 | **4,946 tokens**                      |
| **Mean Cost per Prompt**                  | **$0.0125** ($1.00/1M in, $5.00/1M out)           | **$0.00** (Free, Open-Source)         |

### Domain-by-Domain Score Breakdown

| Specialist Domain | Anthropic Score | Ollama Score | Evaluation Insights |
| :---------------- | :-------------- | :----------- | :------------------ |
| **Telemetry**     | **5.00 / 5.0**  | **5.00 / 5.0** | Both models achieved 100% success when querying and aggregating sensor telemetry snapshots. |
| **Manuals (RAG)** | **5.00 / 5.0**  | **3.75 / 5.0** | Claude delivered complete technical steps citing manual sections; Ollama retrieved correct passages but occasionally gave partial procedural steps. |
| **Business / Orders** | **5.00 / 5.0** | **3.50 / 5.0** | Claude reliably parsed complex quote lines, revisions, and order states; Ollama missed line details on multi-table lookups. |
| **Troubleshooting & Cross-Domain** | **4.38 / 5.0** | **3.13 / 5.0** | Cross-domain tasks (e.g. correlating maintenance tickets with manual procedures) proved the most challenging; Claude achieved mid-success (4.38) while Ollama experienced a failure on composite multi-agent reasoning. |

### Architectural Trade-Offs

- **Cloud Frontier API (`claude-haiku-4-5`)**:
  - *Advantages:* High reasoning capability, zero failures (92% fully successful), reliable tool-calling execution, and 42% lower latency (7.47s vs 12.97s).
  - *Disadvantages:* Incurs operational API costs (~$0.0125/query) and requires external cloud connectivity.
- **Local Edge LLM (`qwen2.5:3b` via Ollama)**:
  - *Advantages:* Complete data sovereignty and privacy (no proprietary industrial telemetry or manual data leaves the plant's on-premises environment) with $0 token cost.
  - *Disadvantages:* Higher latency on standard hardware and higher susceptibility to incomplete answers or failures on compound, multi-agent workflows.

---

## Project Documentation

Further technical specifications, architecture guides, and reference documents are available in the [`documentation/`](documentation/) folder:

- **[AROL Project Presentation (PDF)](documentation/AROL%20Project%20Presentation_Update.pdf):** Full slide deck covering the project overview, high-level architecture, LangGraph multi-agent flow, MCP tool validation, and comparative benchmark results.
- **[ARCHITECTURE.md](documentation/ARCHITECTURE.md):** In-depth technical architecture describing layer separation (Frontend, Django, Orchestrator, MCP Server, Data Layer), security rules, and communication protocols.
- **[ORCHESTRATOR_GUIDE.md](documentation/ORCHESTRATOR_GUIDE.md):** Reference manual for the orchestrator, domain agent roles, routing prompts, and MCP tool schemas.
- **[ORCHESTRATOR_IMPLEMENTATION.md](documentation/ORCHESTRATOR_IMPLEMENTATION.md):** Architectural implementation details covering Stub vs. LangGraph orchestrators, SSE streaming framing, and conversation state persistence.
- **[QR_MACHINE_FOCUS.md](documentation/QR_MACHINE_FOCUS.md):** Technical documentation for physical QR code scanning, deep-linking (`/m/:machineId`), and machine context locking.

---

## Prerequisites

| Component               | Version                              |
| :---------------------- | :----------------------------------- |
| Python                  | 3.12+                                |
| Node.js                 | ≥ 22.12 (required by Vite 8)        |
| PostgreSQL              | 16 (or use the Docker option below)  |
| Docker + Docker Compose | optional, only for the Docker option |

---

## How to Compile and Run

### Option A — Docker Compose (recommended)

From the repository root, create a `.env` file with the variables listed under Execution Parameters below (all have defaults, so an empty or partial `.env` also works), then:

```bash
docker compose up --build
```

This builds and starts three services: `db` (PostgreSQL), `backend` (Django, served by Uvicorn on ASGI), and `frontend` (the built React app, served by nginx). On first boot the backend container automatically waits for PostgreSQL, runs migrations, and loads the fleet dataset from `Backend/static/AROL_Q2_synthetic_fleet_dataset.xlsx` if the database is empty (see `RUN_DB_INIT` below).

Open **http://localhost:8080**.

To use a local Qdrant container instead of Qdrant Cloud / in-memory:

```bash
QDRANT_URL=http://qdrant:6333 QDRANT_API_KEY= docker compose --profile local-qdrant up --build
```

### Option B — Manual (local processes)

#### Database setup

Create the PostgreSQL user and database before starting the backend. Connect as a superuser (e.g. `psql -U postgres`), then run these commands **one at a time**:

**1.** Run only this first:

```sql
CREATE USER arol WITH PASSWORD 'arol';
```

**2.** Then run only this line by itself (highlight it → Ctrl+Enter):

```sql
CREATE DATABASE arol OWNER arol;
```

**3.** Then run:

```sql
GRANT ALL PRIVILEGES ON DATABASE arol TO arol;
```

These match the defaults in `.env` (`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` all set to `arol`).

**1. Backend** — from the repository root:

```bash
cd Backend
python -m venv ../arol_venv && source ../arol_venv/bin/activate   # or your own venv
pip install -r requirements.txt

python manage.py migrate
python initiliaze_database.py            # loads the fleet dataset (see Dataset Formats below)
python manage.py runserver               # starts at http://127.0.0.1:8000
```

**2. Frontend** — in a separate terminal:

```bash
cd frontend
npm install
npm run dev                              # starts at http://localhost:5173, proxies /api to :8000
```

Log in with any user created by `initiliaze_database.py` (default password `changeme`, see below), or seed one directly:

```bash
python manage.py createsuperuser
```

**Compiling the frontend for production** (used by the Docker `frontend` target, or standalone):

```bash
cd frontend
npm run build     # type-checks (tsc -b) then builds to frontend/dist/
```

---

## Execution Parameters

### Environment variables (`.env`, or exported before running)

| Variable                                                    | Default                         | Purpose                                                                                                   |
| :---------------------------------------------------------- | :------------------------------ | :-------------------------------------------------------------------------------------------------------- |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `arol` / `arol` / `arol`  | PostgreSQL connection.                                                                                    |
| `POSTGRES_HOST` / `POSTGRES_PORT`                       | `localhost` / `5432`        | PostgreSQL host/port (Docker Compose overrides`POSTGRES_HOST=db`).                                      |
| `DJANGO_DEBUG`                                            | `true`                        | Django debug mode.                                                                                        |
| `DJANGO_SECRET_KEY`                                       | dev-only default                | Django`SECRET_KEY`; set a real value in production.                                                     |
| `DJANGO_ALLOWED_HOSTS`                                    | `localhost,127.0.0.1,backend` | Comma-separated extra allowed hosts.                                                                      |
| `DJANGO_CSRF_TRUSTED_ORIGINS`                             | ``                              | Comma-separated extra trusted origins for CSRF.                                                           |
| `ORCHESTRATOR_BACKEND`                                    | `stub`                        | Chat orchestrator backend:`stub` (local/CI, no router) or `langgraph` (production multi-agent graph). |
| `LLM_PROVIDER`                                            | `anthropic`                   | `anthropic` or `ollama`.                                                                              |
| `ANTHROPIC_API_KEY`                                       | ``                              | Required when`LLM_PROVIDER=anthropic`.                                                                  |
| `ANTHROPIC_MODEL`                                         | `claude-haiku-4-5-20251001`   | Anthropic model id.                                                                                       |
| `LOCAL_LLM_MODEL`                                         | `qwen2.5:3b`                  | Model name when`LLM_PROVIDER=ollama`.                                                                   |
| `LOCAL_LLM_BASE_URL`                                      | `http://localhost:11434`      | Ollama server URL.                                                                                        |
| `LOCAL_LLM_TEMPERATURE`                                   | `0.0`                         | Ollama sampling temperature.                                                                              |
| `LOCAL_LLM_TIMEOUT`                                       | `60.0`                        | Ollama request timeout (seconds).                                                                         |
| `QDRANT_URL`                                              | `:memory:`                    | Qdrant instance URL, or`:memory:` for an ephemeral local index.                                         |
| `QDRANT_API_KEY`                                          | ``                              | Qdrant Cloud API key (unused for`:memory:` / local Qdrant).                                             |
| `QDRANT_COLLECTION_MANUALS`                               | `arol_manuals_fastembed`      | Qdrant collection name for manual/error-code passages.                                                    |
| `EMBEDDING_MODEL`                                         | `BAAI/bge-small-en-v1.5`      | FastEmbed embedding model.                                                                                |
| `RUN_DB_INIT`                                             | `1`                           | Docker only:`1` auto-loads the fleet dataset on first boot if the database is empty, `0` disables it. |
| `UVICORN_WORKERS`                                         | `1`                           | Docker only: number of Uvicorn worker processes.                                                          |

### Backend management commands (`python manage.py <command>`, run from `Backend/`)

| Command                                                                      | Parameters                                                                                                                                     | Purpose                                                                    |
| :--------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------- |
| `migrate`                                                                  | —                                                                                                                                             | Apply database migrations.                                                 |
| `python initiliaze_database.py` *(standalone script, not `manage.py`)* | `--excel <path>` (default `static/AROL_Q2_synthetic_fleet_dataset.xlsx`), `--flush` (delete existing fleet data first, keeps superusers) | Load the fleet dataset — see Dataset Formats below.                       |
| `python extract_full_manuals.py` *(standalone script, not `manage.py`)*   | `--pdf-dir <path>` (default `../Data/Manuals_pdf`), `--output-dir <path>` (default `../Data/Manuals_md`)                                      | Convert PDF manuals in `Manuals_pdf` to Markdown in `Manuals_md`.         |
| `seed_demo_machine`                                                        | `--username <name>` (default `demo`; must already exist, e.g. from `initiliaze_database.py`)                                             | Attach a demo machine (serial`A3279`) and its units to an existing user. |
| `ingest_markdown_manuals`                                                  | `--dir <path>` (default `Data/Manuals_md`), `--no-clear` (keep existing Qdrant points instead of clearing first)                         | Ingest all Markdown manuals in a directory into Qdrant.                    |
| `ingest_manual`                                                            | `--pdf <path>` (required), `--model <id>` (required), `--chapter <name>` (required), `--section <name>` (required)                     | Ingest a single PDF manual chapter/section into Qdrant.                    |
| `seed_demo_manuals`                                                        | —                                                                                                                                             | Seed a small set of demo manual passages and error codes into Qdrant.      |
| `test apps.mcp_server apps.agents`                                         | —                                                                                                                                             | Run the backend test suite.                                                |

### Frontend npm scripts (run from `frontend/`)

| Script            | Purpose                                                                                                |
| :---------------- | :----------------------------------------------------------------------------------------------------- |
| `npm run dev`   | Start the Vite dev server at`http://localhost:5173` (proxies `/api` to `http://127.0.0.1:8000`). |
| `npm run build` | Type-check (`tsc -b`) and build the production bundle to `frontend/dist/`.                         |

---

## Dataset Formats

### Fleet dataset — Excel workbook

`initiliaze_database.py` loads `Backend/static/AROL_Q2_synthetic_fleet_dataset.xlsx` (or the `--excel` path given). It expects an `.xlsx` workbook with one sheet per entity, sheet name and column headers exactly as below:

| Sheet                  | Columns                                                                                                                                                                            | Notes                                                                                                        |
| :--------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------- |
| `Companies`          | `companyId`, `companyName`, `country`, `sector`, `city`, `currency`, `locale`                                                                                        | `companyId` is the primary key referenced by other sheets.                                                 |
| `Users`              | `userId`, `email`, `firstName`, `lastName`, `companyId`, `jobTitle`, `visibility`                                                                                    | `visibility` must be one of `full`, `technician`, `commercial`. New users get password `changeme`. |
| `MachineModels`      | `modelId`, `modelCode`, `description`, `primitiveDiameter`, `nominalHeads`, `containerType`, `capType`, `industrySegment`, `notes`                               | `primitiveDiameter` and `notes` may be blank.                                                            |
| `Machines`           | `machineId`, `companyId`, `modelId`, `serialNumber`, `deliveryDate`, `plantLocation`, `configurationProfile`, `plcFamily`, `softwareVersion`                     | `softwareVersion` may be blank. Dates as Excel dates or `YYYY-MM-DD`.                                    |
| `Quotes`             | `quoteId`, `companyId`, `currency`, `createdAt`, `validUntil`, `description`                                                                                           |                                                                                                              |
| `QuoteRevisions`     | `quoteRevisionId`, `quoteId`, `revisionNumber`, `revisionStatus`, `issuedAt`, `discountRate`, `changeSummary`                                                        |                                                                                                              |
| `QuoteLines`         | `quoteLineId`, `quoteRevisionId`, `machineId`, `price`, `description`                                                                                                    | `machineId` may be blank (line not tied to an installed machine).                                          |
| `Orders`             | `orderId`, `quoteId`, `companyId`, `orderStatus`, `orderDate`, `expectedDeliveryDate`, `shipmentStatus`, `currency`, `notes`                                     | `notes` may be blank.                                                                                      |
| `OrderLines`         | `orderLineId`, `orderId`, `fulfillmentStatus`                                                                                                                                |                                                                                                              |
| `TelemetrySnapshots` | `telemetryId`, `machineId`, `timestamp`, `operationalStatus`, `productionRateBph`, `uptimePercentage`, `alarmCount`, `temperatureC`, `energyKwh`, `healthNote` | `timestamp` as Excel datetime; naive timestamps are treated as UTC.                                        |
| `Alarms`             | `alarmId`, `machineId`, `timestamp`, `alarmCode`, `severity`, `alarmStatus`                                                                                            |                                                                                                              |
| `MaintenanceTickets` | `ticketId`, `machineId`, `alarmId`, `ticketType`, `ticketStatus`, `priority`, `createdDate`, `ownerRole`                                                           | `alarmId` may be blank (ticket not linked to an alarm).                                                    |

Re-running the import is idempotent (rows are matched by their id column and updated in place); pass `--flush` to wipe existing fleet/quote/order data (superusers are kept) before a clean reload.

### Manual documents — Markdown (for RAG ingestion)

`ingest_markdown_manuals` reads every `.md` file under a directory (default `Data/Manuals_md`) and expects:

- Structural headers using `#`, `##`, `###` to delimit chapters/sections (used as retrieval metadata).
- Page boundaries marked with an HTML comment: `<!-- Page N -->` (N = page number in the source document).
- The machine/model a file belongs to is inferred from its filename (a small built-in mapping handles a few known filenames; otherwise the file stem, uppercased, is used as the machine/model identifier).

`ingest_manual` instead ingests one PDF file at a time (`--pdf`), tagging every chunk with the given `--model`, `--chapter`, and `--section`.
