"""Schemas for telemetry queries (Telemetry Agent)."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import ScopedContext


class QueryTelemetryInput(ScopedContext):
    metric: str = Field(
        ...,
        min_length=1,
        description='Metric name, e.g. cycle_count, temperature, pressure.',
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


class TelemetryPoint(BaseModel):
    ts: datetime
    metric: str
    value: float
    unit: str | None = None


class QueryTelemetryOutput(BaseModel):
    metric: str
    points: list[TelemetryPoint]
