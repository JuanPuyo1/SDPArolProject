"""Pydantic I/O schemas for MCP tools."""

from .business import ListSparePartsInput, ListSparePartsOutput, SparePartItem
from .common import ScopedContext, ToolError, ToolResponse
from .echo import EchoInput, EchoOutput
from .machine import (
    GetMachineInfoInput,
    GetMachineInfoOutput,
    ListCustomerMachinesInput,
    ListCustomerMachinesOutput,
    MachineSummary,
)
from .manual import ManualHit, SearchManualInput, SearchManualOutput
from .telemetry import QueryTelemetryInput, QueryTelemetryOutput, TelemetryPoint
from .ticket import CreateTicketInput, CreateTicketOutput
from .troubleshooting import ErrorCodeHit, SearchErrorCodesInput, SearchErrorCodesOutput

__all__ = [
    'ScopedContext',
    'ToolError',
    'ToolResponse',
    'EchoInput',
    'EchoOutput',
    'GetMachineInfoInput',
    'GetMachineInfoOutput',
    'ListCustomerMachinesInput',
    'ListCustomerMachinesOutput',
    'MachineSummary',
    'SearchManualInput',
    'SearchManualOutput',
    'ManualHit',
    'QueryTelemetryInput',
    'QueryTelemetryOutput',
    'TelemetryPoint',
    'CreateTicketInput',
    'CreateTicketOutput',
    'SearchErrorCodesInput',
    'SearchErrorCodesOutput',
    'ErrorCodeHit',
    'ListSparePartsInput',
    'ListSparePartsOutput',
    'SparePartItem',
]
