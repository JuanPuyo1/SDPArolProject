# SDP AROL — Test Report

**Date:** 24 August 2026  
**Spec:** `README_AROL.md` (Politecnico di Torino / AROL S.p.A. Project Q2)  
**Also checked:** prior chat work (QR machine focus, visibility, multi-agent orchestrator, MCP tools)

## How to run

From `Backend/`, using the repo venv (isolated SQLite + in-memory Qdrant; no live LLM / production Qdrant):

```bash
cd Backend
../.venv/bin/python manage.py test --settings=config.test_settings
```

The local Postgres role cannot `CREATE DATABASE`, so `config/test_settings.py` uses a file-backed SQLite test DB. WhiteNoise (added for Docker) is stripped in test settings so the suite does not require that extra package.

## Run result (this execution)

| | Count |
|---|---|
| **Total** | 102 |
| **Passed** | 98 |
| **Failed** | 3 |
| **Skipped** | 1 (`langchain_ollama` not installed in `.venv`) |
| **Runtime** | ~1.1 s |

**Verdict: the platform covers the AROL Access Model, fleet/QR lookup, and MCP tool layer well. Remaining spec gaps: RAG tenant leak, order amount from `Approved` revision.**

---

## Spec coverage (`README_AROL.md`)

### Access Model — **mostly PASS**

Both checks are implemented: `companyId` tenant boundary + `visibility` (`full` / `technician` / `commercial`).

| Requirement | Status | Evidence |
|---|---|---|
| Tenant boundary never crossed | **PASS** | HTTP machine/order APIs and MCP tools return `FORBIDDEN` for another company's machine; `list_customer_machines` never includes foreign serials |
| Machine identity + manuals visible to every role | **PASS** | `full`, `technician`, and `commercial` can `GET /api/machines/` and `get_machine_info` |
| Operational data (telemetry, alarms, tickets) = `full` + `technician` | **PASS** | HTTP `/api/machines/tickets/` and MCP `query_telemetry` / `list_alarms` / `list_maintenance_tickets` |
| Commercial data (quotes, orders) = `full` + `commercial` | **PASS** | HTTP `/api/quotes/orders/` and MCP `get_quote_history` / `get_order_status` |
| Out-of-scope declined explicitly (not empty “not found”) | **PASS** | Machine REST and chat: 403 if the machine exists but is not owned, 404 if unknown. MCP tools return `FORBIDDEN`. |
| Own `Companies` / `Users` row | **PASS** | Login/profile returns `company_id`, `visibility`, `user_id` |

## Failed tests (product gaps)

1. **`apps.mcp_server.tests.RagManualSearchTests.test_search_does_not_return_another_machines_exclusive_manual`**  
   Remove (or tightly constrain) the unfiltered retry in `apps/mcp_server/rag_engine/search.py` `_query_manuals`. Keep the `AROL_GENERAL` / general-catalogue `should` clauses; do not search the whole collection.

2. **`apps.quotes.tests.QuoteConventionTests.test_order_amount_comes_from_approved_revision_not_later_rejected`**  
   In `apps/mcp_server/orders_data.py`, select the **Approved** revision (controlled vocabulary), not `'accepted'` / latest `issued_at`.

### Dataset domains / models — **PASS**

ORM models match the workbook sheets: Companies, Users, MachineModels, Machines, Quotes, QuoteRevisions, QuoteLines, Orders, OrderLines, TelemetrySnapshots, Alarms, MaintenanceTickets.

Covered conventions:

- `QuoteLines` belong to a **revision** (no `quoteId` on the line)
- `QuoteLines.price` is **not** discounted a second time
- `OrderLines` carry **fulfilment only** (no item/qty/price)
- Empty optional FKs are kept (`QuoteLines.machineId`, `MaintenanceTickets.alarmId`, `MachineModels.primitiveDiameter`)
- Company with users but **no machines** returns an empty fleet list (legitimate empty, not a denial)
- Quotes that never became orders, and a quote whose **final revision is Rejected**, are representable
- Manual filename convention: `<serialNumber>_manual_EN.pdf`
- `Machines.configurationProfile` is exposed (nominal rate / voltage live here, not on the model)
- Alarm code form exercised (`AL017_LOW_AIR_PRESSURE`)
- Telemetry: idle interval has `productionRateBph = 0` and `uptimePercentage = 0`

### Heterogeneous sources (tables + manuals) — **PASS with one leak**

- Structured lookups go through MCP tools / ORM.
- Unstructured manuals go through Qdrant RAG (`search_manual` / `search_error_codes`).
- Ingestion + page-number payload works in-memory.

Failed test: `RagManualSearchTests.test_search_does_not_return_another_machines_exclusive_manual`.  
`rag_engine/search.py` retries **without** the `machine_serial` filter when the scoped search is empty, so another machine’s exclusive manual can leak. Spec: manuals are **machine-specific**.

### Commercial order amount — **FAIL**

Failed test: `QuoteConventionTests.test_order_amount_comes_from_approved_revision_not_later_rejected`.

Spec: order content comes from the **Approved** revision’s quote lines.  
Code (`orders_data._order_revision`) looks for status `'accepted'` (not in the controlled vocabulary) and then falls back to the **latest issued** revision. A later `Rejected` revision therefore prices the order (1.00 instead of 1000.00).

Fix: match `revision_status.lower() == "approved"` (and prefer highest `revision_number` among Approved).

### AI architecture — **PASS**

Specialized agents exist and are routed by LangGraph (or Stub for local/CI):

| Agent | Tools | Tests |
|---|---|---|
| Shared | `get_machine_info`, `list_customer_machines`, `echo` | registry + scoping |
| Manuals | `search_manual` | agent tool set + RAG |
| Telemetry | `query_telemetry` | agent + MCP |
| Troubleshooting / Service | `search_error_codes`, `list_alarms`, `create_ticket`, `list_maintenance_tickets` | agent + MCP |
| Business | `get_quote_history`, `get_order_status`, `list_spare_parts` | agent + MCP |

OrchestratorPort, SSE (`step` / `tool` / `token` / `done`), session continuity, and `customer_id` taken from the **session** (never the client body) all pass.

### QR codes — **PASS (backend)**

`GET /api/machines/<id>/` accepts **serial number or `machineId`**, returns 403 for another tenant. That is the resolve API used after scan / `/m/:id` / fleet pick.

Frontend QR/select/nav-gate is implemented (see chat-history section) but was **not** exercised with a browser in this Python suite.

### Stubs vs ready (implementation status, tests document current behaviour)

| Tool | Registry status | Notes |
|---|---|---|
| `create_ticket` | **stub** | Returns a `TKT-…` id but **does not persist** a `MaintenanceTicket` |
| `list_spare_parts` | **stub** | Placeholder catalog; no real parts data |
| All other registered tools | **ready** | ORM or Qdrant backed |

There is **no HTTP list of quotes** (only `/api/quotes/orders/`). Quote history is available to agents via MCP `get_quote_history`.

---

## Chat-history checklist (what was asked vs what exists)

From prior sessions (QR focus, visibility, agents, MCP):

| Expected | Implemented? | Notes |
|---|---|---|
| Welcome/select: scan QR **or** pick from fleet | **Yes** (frontend) | `/select`, `/scan`, `/m/:id` |
| Machine / manual / chat / maintenance scoped to focus machine | **Yes** | `RequireMachineRoute` / `MachineFocusGate`; chat sends `machine_serial` |
| Hide full nav until a machine is selected | **Yes** | NavBar + focus gate |
| Chat context = selected machine for orchestrator/MCP | **Yes** | `customer_id` from session user; serial from body, re-checked in MCP |
| `sessionStorage` focus pointer; `localStorage` chat UI cache | **Yes** | Documented in `documentation/QR_MACHINE_FOCUS.md` |
| Visibility: commercial vs technician vs full | **Yes** | HTTP + MCP `visibility_domain` |
| Multi-agent LangGraph + Stub | **Yes** | Factory switch; tests mock the LLM |
| Fleet-wide `target_machine_serial` on tools | **No (disabled)** | Commented out in `agent_kit.py`. Current design: **hard-scoped to the focus serial**. QR doc §4 is stale. |
| `list_customer_machines` on every agent | **No (disabled)** | Same change; agents only get their domain tools |
| Spare-parts catalog | **Stub** | |
| Persist `create_ticket` | **No** | Stub only |
| Cost/token logging in `core` | **Not verified / not wired in tests** | Still a platform follow-up |

---

## Failed tests (product gaps)

1. **`apps.mcp_server.tests.RagManualSearchTests.test_search_does_not_return_another_machines_exclusive_manual`**  
   Remove (or tightly constrain) the unfiltered retry in `apps/mcp_server/rag_engine/search.py` `_query_manuals`. Keep the `AROL_GENERAL` / general-catalogue `should` clauses; do not search the whole collection.

2. **`apps.quotes.tests.QuoteConventionTests.test_order_amount_comes_from_approved_revision_not_later_rejected`**  
   In `apps/mcp_server/orders_data.py`, select the **Approved** revision (controlled vocabulary), not `'accepted'` / latest `issued_at`.

---

## What was not tested here

- Frontend (React routes, camera QR, `sessionStorage` / `localStorage`) — Python-only as requested  
- Live Claude / Ollama / production Qdrant  
- Full Excel import (`initiliaze_database.py`) against the real workbook  
- End-to-end LLM answers to the example research questions (alarm meaning, spare parts, safety procedures) — those need a live model + ingested manuals  
- WhiteNoise / Docker image (being added in a parallel track)

---

## Test map (where to look)

| Area | File |
|---|---|
| Shared AROL fixtures | `Backend/apps/core/test_fixtures.py` |
| Auth + visibility HTTP | `Backend/apps/authentication/tests.py` |
| Fleet, QR lookup, manuals, tickets | `Backend/apps/machines/tests.py` |
| Quotes / orders conventions | `Backend/apps/quotes/tests.py` |
| MCP tools, tenant, RAG | `Backend/apps/mcp_server/tests.py` |
| SSE, stub, LangGraph, LLM factory | `Backend/apps/agents/tests.py` |
| Isolated runner | `Backend/config/test_settings.py` |
