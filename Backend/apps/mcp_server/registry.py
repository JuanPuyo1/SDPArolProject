"""
MCP tool registry: discovery + invocation.

LangGraph / StubOrchestrator must call tools only through this module
(or the optional HTTP debug endpoints that wrap it). Do not query the ORM
from agent/graph code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from apps.mcp_server.schemas.business import ListSparePartsInput, ListSparePartsOutput
from apps.mcp_server.schemas.common import ToolError
from apps.mcp_server.schemas.echo import EchoInput, EchoOutput
from apps.mcp_server.schemas.machine import (
    GetMachineInfoInput,
    GetMachineInfoOutput,
    ListCustomerMachinesInput,
    ListCustomerMachinesOutput,
)
from apps.mcp_server.schemas.manual import SearchManualInput, SearchManualOutput
from apps.mcp_server.schemas.telemetry import QueryTelemetryInput, QueryTelemetryOutput
from apps.mcp_server.schemas.ticket import CreateTicketInput, CreateTicketOutput
from apps.mcp_server.schemas.troubleshooting import (
    SearchErrorCodesInput,
    SearchErrorCodesOutput,
)
from apps.mcp_server.scoping import ScopeError
from apps.mcp_server.tools import (
    create_ticket,
    echo,
    get_machine_info,
    list_customer_machines,
    list_spare_parts,
    query_telemetry,
    search_error_codes,
    search_manual,
)

ToolStatus = Literal['ready', 'stub']
AgentName = Literal[
    'shared',
    'manuals',
    'telemetry',
    'business',
    'troubleshooting',
    'service',
]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[Any], BaseModel]
    agent: AgentName
    status: ToolStatus
    requires_machine_scope: bool


_TOOLS: dict[str, ToolSpec] = {
    'echo': ToolSpec(
        name='echo',
        description='Debug tool: returns the input message (and optional scope fields).',
        input_model=EchoInput,
        output_model=EchoOutput,
        handler=echo,
        agent='shared',
        status='ready',
        requires_machine_scope=False,
    ),
    'get_machine_info': ToolSpec(
        name='get_machine_info',
        description='Return the full machine record for customer_id + machine_serial.',
        input_model=GetMachineInfoInput,
        output_model=GetMachineInfoOutput,
        handler=get_machine_info,
        agent='shared',
        status='ready',
        requires_machine_scope=True,
    ),
    'list_customer_machines': ToolSpec(
        name='list_customer_machines',
        description='List machines owned by customer_id (fleet summary).',
        input_model=ListCustomerMachinesInput,
        output_model=ListCustomerMachinesOutput,
        handler=list_customer_machines,
        agent='shared',
        status='ready',
        requires_machine_scope=False,
    ),
    'search_manual': ToolSpec(
        name='search_manual',
        description='Search the machine manual / RAG index for relevant passages.',
        input_model=SearchManualInput,
        output_model=SearchManualOutput,
        handler=search_manual,
        agent='manuals',
        status='stub',
        requires_machine_scope=True,
    ),
    'query_telemetry': ToolSpec(
        name='query_telemetry',
        description='Query recent telemetry points for a metric on the scoped machine.',
        input_model=QueryTelemetryInput,
        output_model=QueryTelemetryOutput,
        handler=query_telemetry,
        agent='telemetry',
        status='stub',
        requires_machine_scope=True,
    ),
    'list_spare_parts': ToolSpec(
        name='list_spare_parts',
        description='Search spare parts / catalog for the scoped machine.',
        input_model=ListSparePartsInput,
        output_model=ListSparePartsOutput,
        handler=list_spare_parts,
        agent='business',
        status='stub',
        requires_machine_scope=True,
    ),
    'search_error_codes': ToolSpec(
        name='search_error_codes',
        description='Look up error codes / alarms and recommended troubleshooting steps.',
        input_model=SearchErrorCodesInput,
        output_model=SearchErrorCodesOutput,
        handler=search_error_codes,
        agent='troubleshooting',
        status='stub',
        requires_machine_scope=True,
    ),
    'create_ticket': ToolSpec(
        name='create_ticket',
        description='Open a field-support / service ticket for the scoped machine.',
        input_model=CreateTicketInput,
        output_model=CreateTicketOutput,
        handler=create_ticket,
        agent='service',
        status='stub',
        requires_machine_scope=True,
    ),
}


def list_tools(*, agent: str | None = None) -> list[dict[str, Any]]:
    """
    Return tool metadata for orchestrator discovery.

    Optionally filter by owning agent name (e.g. ``manuals``).
    """
    specs = _TOOLS.values()
    if agent is not None:
        specs = [s for s in specs if s.agent == agent or s.agent == 'shared']

    return [
        {
            'name': s.name,
            'description': s.description,
            'agent': s.agent,
            'status': s.status,
            'requires_machine_scope': s.requires_machine_scope,
            'input_schema': s.input_model.model_json_schema(),
            'output_schema': s.output_model.model_json_schema(),
        }
        for s in specs
    ]


def get_tool(name: str) -> ToolSpec | None:
    return _TOOLS.get(name)


def invoke(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Validate ``params`` against the tool's Pydantic input model and run the handler.

    Always returns a JSON-serializable dict:
      - success: ``{"status": "ok", "data": {...}}``
      - failure: ``{"status": "error", "message": "...", "code": "..."}``
    """
    params = params or {}
    spec = _TOOLS.get(name)
    if spec is None:
        return ToolError(
            message=f'Unknown tool: {name!r}.',
            code='UNKNOWN_TOOL',
        ).model_dump()

    try:
        validated = spec.input_model.model_validate(params)
    except ValidationError as exc:
        return ToolError(
            message=str(exc),
            code='VALIDATION_ERROR',
        ).model_dump()

    try:
        result = spec.handler(validated)
    except ScopeError as exc:
        return ToolError(message=exc.message, code=exc.code).model_dump()
    except Exception as exc:  # noqa: BLE001 — surface to orchestrator as structured error
        return ToolError(
            message=f'Tool {name!r} failed: {exc}',
            code='TOOL_ERROR',
        ).model_dump()

    if isinstance(result, BaseModel):
        data = result.model_dump(mode='json')
    else:
        data = result

    return {'status': 'ok', 'data': data}
