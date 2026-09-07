# SDPArolProject

Instructions to compile/run the project, its execution parameters, and the input dataset formats it expects.

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
