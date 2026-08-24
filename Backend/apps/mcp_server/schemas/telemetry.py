"""Schemas for telemetry queries (Telemetry Agent)."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import ScopedContext


class QueryTelemetryInput(ScopedContext):
    metric: str = Field(
        ...,
        min_length=1,
        description='Metric name, e.g. temperature, production_rate, uptime, alarm_count, energy.',
    )
    from_ts: datetime | None = Field(
        default=None,
        description='Optional start of time window (ISO-8601).',
    )
    to_ts: datetime | None = Field(
        default=None,
        description='Optional end of time window (ISO-8601).',
    )
    limit: int = Field(default=50, ge=1, le=500)
    include_points: bool = Field(
        default=True,
        description='Return individual telemetry points (up to limit). Set false when only aggregates are needed.',
    )
    include_aggregates: bool = Field(
        default=False,
        description=(
            'Compute count, min, max, avg, and sum over the full time window '
            '(not limited by limit). Set true when the user asks for averages, '
            'totals, min/max, or how many readings exist.'
        ),
    )


class TelemetryPoint(BaseModel):
    ts: datetime
    metric: str
    value: float
    unit: str | None = None
    operational_status: str


class TelemetryAggregates(BaseModel):
    count: int
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    sum: float | None = None
    unit: str | None = None
    operational_statuses: list[str] = Field(default_factory=list)


class QueryTelemetryOutput(BaseModel):
    metric: str
    points: list[TelemetryPoint] = Field(default_factory=list)
    aggregates: TelemetryAggregates | None = None
