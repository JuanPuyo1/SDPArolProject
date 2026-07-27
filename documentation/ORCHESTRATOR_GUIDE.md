# MCP Orchestrator Tool Guide — Arol Customer Platform

**Audience:** LangGraph / agent partners building **Manuals**, **Telemetry**, and **Business** agents (and Esteban’s **Troubleshooting** + **Service** agents).

**Source of truth:** `Backend/apps/mcp_server/` — call tools only via `registry.invoke`. Never use Django ORM or SQL inside agent/graph nodes.

---

## 1. How agents talk to tools

```
Chat / SSE (Django apps.agents)
        ↓
OrchestratorPort (Stub or LangGraph)
        ↓
MCP registry.invoke(tool_name, params)
        ↓
tools/*  →  machines / rag_engine / … (behind tools only)
```

### Python (in-process — preferred for LangGraph nodes)

```python
from apps.mcp_server import registry

# Discover
tools = registry.list_tools()                    # all tools
tools = registry.list_tools(agent="manuals")     # manuals + shared

# Invoke
result = registry.invoke(
    "get_machine_info",
    {"customer_id": "demo", "machine_serial": "A3279"},
)

if result["status"] == "ok":
    machine = result["data"]["machine"]
else:
    # result["message"], optional result["code"]
    ...
```

### HTTP debug (local only, `DEBUG=True`)

| Method | URL | Purpose |
|--------|-----|---------|
| `GET` | `/api/mcp/tools/` | List tools (+ `?agent=manuals`) |
| `POST` | `/api/mcp/tools/<name>/invoke/` | Invoke with JSON body |

```bash
curl http://127.0.0.1:8000/api/mcp/tools/
curl -X POST http://127.0.0.1:8000/api/mcp/tools/echo/invoke/ \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"ping\"}"
```

HTTP invoke is gated by `MCP_HTTP_INVOKE_ENABLED` (defaults to `DEBUG`). Turn it off in production; agents must use in-process `registry.invoke`.

---

## 2. Hard rules (non-negotiable)

1. **Every tenant-scoped call** must include `customer_id` and `machine_serial` (except `echo` and `list_customer_machines`).
2. Tools **re-validate ownership**. Cross-tenant access returns `{"status":"error","code":"FORBIDDEN"}`.
3. **No ORM in the graph.** If you need data, add or call an MCP tool.
4. Treat `status: "stub"` tools as contract-stable: same inputs/outputs; data will become real later (`stub: true` in payload until then).
5. On errors, use the envelope — do not invent side channels:

```json
{"status": "error", "message": "...", "code": "NOT_FOUND|FORBIDDEN|VALIDATION_ERROR|UNKNOWN_TOOL|TOOL_ERROR"}
```

Success:

```json
{"status": "ok", "data": { ... }}
```

### Identity

| Field | Meaning |
|-------|---------|
| `customer_id` | Django **username** or numeric user **id** as string |
| `machine_serial` | e.g. `A3279` |

Demo seed: user `demo`, serial `A3279` (`python manage.py seed_demo_machine`).

---

## 3. Tool catalog by agent

| Tool | Agent | Status | Scope | One-line purpose |
|------|-------|--------|-------|------------------|
| `echo` | shared | ready | optional | Connectivity / debug |
| `get_machine_info` | shared | ready | customer + serial | Full machine record |
| `list_customer_machines` | shared | ready | customer only | Fleet list |
| `search_manual` | **manuals** | stub | customer + serial | Manual / RAG passages |
| `query_telemetry` | **telemetry** | stub | customer + serial | Metric time series |
| `list_spare_parts` | **business** | stub | customer + serial | Spare parts catalog |
| `search_error_codes` | **troubleshooting** | stub | customer + serial | Alarms + recommended steps |
| `create_ticket` | **service** | stub | customer + serial | Open support ticket |

`registry.list_tools(agent="manuals")` returns that agent’s tools **plus** all `shared` tools.

---

## 4. Tool reference

### `echo` (shared · ready)

**When:** Smoke tests, wiring checks.  
**Input:**

```json
{ "message": "ping", "customer_id": "demo", "machine_serial": "A3279" }
```

`customer_id` / `machine_serial` are optional and only echoed.

---

### `get_machine_info` (shared · ready)

**When:** Need model, units, electrical/pneumatic data, manual URL, etc.  
**Input:**

```json
{ "customer_id": "demo", "machine_serial": "A3279" }
```

**Output `data.machine`:** same camelCase shape as `GET /api/machines/<serial>/` (serialNumber, identification, technicalData, mainUnits, …).

---

### `list_customer_machines` (shared · ready)

**When:** User has multiple machines; pick context before chat.  
**Input:**

```json
{ "customer_id": "demo" }
```

**Output:** `{ "machines": [ { "id", "serial_number", "model", "full_model", "manufacturing_year" } ] }`

---

### `search_manual` (manuals · stub)

**Owner:** Manuals Agent  
**When:** Procedures, safety, maintenance steps from the digital manual.  
**Input:**

```json
{
  "customer_id": "demo",
  "machine_serial": "A3279",
  "query": "how to adjust capping torque",
  "top_k": 5
}
```

**Output:** `{ "stub": true, "query", "hits": [ { "title", "section", "excerpt", "page", "score", "source" } ], "note" }`

Until `rag_engine` is live, one stub hit is returned so the graph can keep flowing.

---

### `query_telemetry` (telemetry · stub)

**Owner:** Telemetry Agent  
**When:** Live/recent machine signals (cycles, temp, pressure, …).  
**Input:**

```json
{
  "customer_id": "demo",
  "machine_serial": "A3279",
  "metric": "cycle_count",
  "from_ts": null,
  "to_ts": null,
  "limit": 50
}
```

**Output:** `{ "stub": true, "metric", "points": [ { "ts", "metric", "value", "unit" } ], "note" }`

---

### `list_spare_parts` (business · stub)

**Owner:** Business Agent  
**When:** Upsell / recommend parts for a unit or symptom.  
**Input:**

```json
{
  "customer_id": "demo",
  "machine_serial": "A3279",
  "query": "closure gripper",
  "limit": 10
}
```

**Output:** `{ "stub": true, "query", "parts": [ { "part_number", "name", "unit_code", "description", "availability" } ], "note" }`

---

### `search_error_codes` (troubleshooting · stub)

**Owner:** Troubleshooting Agent (Esteban)  
**When:** HMI alarm / error code / symptom → diagnosis + actions.  
**Input:**

```json
{
  "customer_id": "demo",
  "machine_serial": "A3279",
  "query": "E042 star-wheel jam",
  "top_k": 5
}
```

**Output:** `{ "stub": true, "query", "hits": [ { "code", "title", "severity", "summary", "recommended_actions" } ], "note" }`

Typical follow-up: call `search_manual` with the same query for procedure text.

---

### `create_ticket` (service · stub)

**Owner:** Service Agent (Esteban)  
**When:** Escalate to field support / maintenance.  
**Input:**

```json
{
  "customer_id": "demo",
  "machine_serial": "A3279",
  "subject": "Star-wheel jam recurring",
  "description": "Alarm E042 three times this shift after washdown.",
  "priority": "high",
  "category": "support"
}
```

`priority`: `low` | `medium` | `high` | `critical`  
`category`: `support` | `maintenance` | `spare_parts` | `other`

**Output:** `{ "stub": true, "ticket_id", "subject", "priority", "status": "open", "note" }`  
No persistence yet — `ticket_id` is generated for contract testing.

---

## 5. Suggested agent routing

| User intent | Primary tool(s) | Optional follow-up |
|-------------|-----------------|--------------------|
| “What machine is this?” | `get_machine_info` | — |
| “My fleet” | `list_customer_machines` | then set `machine_serial` |
| “How do I … / show manual” | `search_manual` | `get_machine_info` for manual URL |
| “What is the temperature / cycles?” | `query_telemetry` | — |
| “Order / find spare part” | `list_spare_parts` | `create_ticket` (category `spare_parts`) |
| “Alarm E0xx / not starting” | `search_error_codes` | `search_manual`, `query_telemetry` |
| “Send a technician” | `create_ticket` | attach findings from other tools in `description` |

Always keep `customer_id` + `machine_serial` in graph state and pass them into every scoped tool call.

---

## 6. LangGraph adapter sketch

```python
from apps.mcp_server import registry

def mcp_tool_node(state: dict) -> dict:
    name = state["pending_tool"]
    params = {
        "customer_id": state["customer_id"],
        "machine_serial": state["machine_serial"],
        **state.get("tool_args", {}),
    }
    # list_customer_machines / echo: drop machine_serial if not needed
    result = registry.invoke(name, params)
    return {"last_tool_result": result}
```

Reuse Pydantic schemas from `apps.mcp_server.schemas` for LLM tool definitions — do not duplicate field lists in the graph package.

```python
from apps.mcp_server.schemas.manual import SearchManualInput

schema = SearchManualInput.model_json_schema()  # for tool binding
```

Or use `registry.list_tools()` → each item’s `input_schema` / `output_schema`.

---

## 7. Ownership map (who builds what)

| Agent | Partner | Tools to rely on |
|-------|---------|------------------|
| Manuals | Partners | `search_manual` (+ shared) |
| Telemetry | Partners | `query_telemetry` (+ shared) |
| Business | Partners | `list_spare_parts` (+ shared) |
| Troubleshooting | Esteban | `search_error_codes` (+ shared, often + `search_manual`) |
| Service | Esteban | `create_ticket` (+ shared) |

Shared tools are available to **all** agents. New domain capabilities → new tool in `mcp_server` + entry in this guide; do not bypass the registry.

---

## 8. Extending the catalog

1. Add Pydantic models under `schemas/`.
2. Implement handler under `tools/`.
3. Register a `ToolSpec` in `registry.py` (`agent`, `status`, schemas, handler).
4. Update this guide’s catalog table.
5. Prefer `status="stub"` until backend data exists; keep I/O stable.

---

## 9. Quick local check

```bash
cd Backend
python manage.py test apps.mcp_server
python manage.py seed_demo_machine   # needs user "demo"
python manage.py shell -c "from apps.mcp_server import registry; print(registry.invoke('get_machine_info', {'customer_id':'demo','machine_serial':'A3279'}))"
```
