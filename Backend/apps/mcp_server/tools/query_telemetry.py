"""query_telemetry — machine telemetry lookup for Telemetry Agent, backed by the ORM."""

from apps.mcp_server import telemetry_data
from apps.mcp_server.schemas.telemetry import (
    QueryTelemetryInput,
    QueryTelemetryOutput,
    TelemetryAggregates,
    TelemetryPoint,
)
from apps.mcp_server.scoping import get_owned_machine


def query_telemetry(params: QueryTelemetryInput) -> QueryTelemetryOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    points: list[TelemetryPoint] = []
    if params.include_points:
        raw_points = telemetry_data.query_telemetry(
            machine,
            metric=params.metric,
            from_ts=params.from_ts,
            to_ts=params.to_ts,
            limit=params.limit,
        )
        points = [TelemetryPoint(**p) for p in raw_points]

    aggregates: TelemetryAggregates | None = None
    if params.include_aggregates:
        raw_agg = telemetry_data.query_telemetry_aggregates(
            machine,
            metric=params.metric,
            from_ts=params.from_ts,
            to_ts=params.to_ts,
        )
        aggregates = TelemetryAggregates(
            count=raw_agg['count'],
            min=raw_agg['min'],
            max=raw_agg['max'],
            avg=raw_agg['avg'],
            sum=raw_agg['sum'],
            unit=raw_agg['unit'],
            operational_statuses=raw_agg['operational_statuses'],
        )

    return QueryTelemetryOutput(
        metric=params.metric,
        points=points,
        aggregates=aggregates,
    )
