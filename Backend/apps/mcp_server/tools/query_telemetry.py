"""query_telemetry — telemetry stub for Telemetry Agent."""

from datetime import UTC, datetime

from apps.mcp_server.schemas.telemetry import (
    QueryTelemetryInput,
    QueryTelemetryOutput,
    TelemetryPoint,
)
from apps.mcp_server.scoping import get_owned_machine


def query_telemetry(params: QueryTelemetryInput) -> QueryTelemetryOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    now = datetime.now(tz=UTC)
    points = [
        TelemetryPoint(
            ts=now,
            metric=params.metric,
            value=0.0,
            unit=None,
        )
    ][: params.limit]
    return QueryTelemetryOutput(metric=params.metric, points=points)
