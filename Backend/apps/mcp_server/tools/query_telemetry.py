"""query_telemetry — telemetry tool for Telemetry Agent."""

from apps.mcp_server.schemas.telemetry import (
    QueryTelemetryInput,
    QueryTelemetryOutput,
    TelemetryPoint,
)
from apps.mcp_server.scoping import get_owned_machine
from apps.mcp_server.telemetry_data import get_store


def query_telemetry(params: QueryTelemetryInput) -> QueryTelemetryOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    raw_points = get_store().query_telemetry(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
        metric=params.metric,
        from_ts=params.from_ts,
        to_ts=params.to_ts,
        limit=params.limit,
    )
    points = [TelemetryPoint(**p) for p in raw_points]
    return QueryTelemetryOutput(
        stub=False,
        metric=params.metric,
        points=points,
        note='query_telemetry returns CSV-backed sensor telemetry data.',
    )
