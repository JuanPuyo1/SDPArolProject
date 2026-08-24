"""ORM-backed data access for telemetry queries (Telemetry Agent).

Reads real TelemetrySnapshot rows (apps.machines.models) for a scoped
machine. Only numeric snapshot fields can be requested as a "metric" --
QueryTelemetryOutput's TelemetryPoint.value is a float -- but every point
also carries the snapshot's operational_status (Running, Idle, Stopped,
Alarm, Maintenance, Size change), since a statistic computed across periods
the machine wasn't actually Running is misleading without that context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import Avg, Count, Max, Min, QuerySet, Sum

from apps.machines.models import Machine, TelemetrySnapshot

# metric alias -> (TelemetrySnapshot field name, unit). Every alias here maps
# to a field that genuinely exists on TelemetrySnapshot -- there is no
# pressure, vibration, or per-cycle-count reading in the data model, so
# those must not be listed (see _resolve_metric: an unmapped metric is a
# hard error now, never a silent substitute).
METRIC_MAP: dict[str, tuple[str, str | None]] = {
    'temperature': ('temperature_c', '°C'),
    'motor_temperature': ('temperature_c', '°C'),
    'temperature_c': ('temperature_c', '°C'),
    'temp': ('temperature_c', '°C'),
    'production_rate': ('production_rate_bph', 'BPH'),
    'production_rate_bph': ('production_rate_bph', 'BPH'),
    'speed': ('production_rate_bph', 'BPH'),
    'operating_speed': ('production_rate_bph', 'BPH'),
    'uptime': ('uptime_percentage', '%'),
    'uptime_percentage': ('uptime_percentage', '%'),
    'alarm_count': ('alarm_count', 'count'),
    'alarms': ('alarm_count', 'count'),
    'energy': ('energy_kwh', 'kWh'),
    'energy_kwh': ('energy_kwh', 'kWh'),
    'power': ('energy_kwh', 'kWh'),
}


def _resolve_metric(metric: str) -> tuple[str, str | None]:
    key = metric.strip().lower()
    if key not in METRIC_MAP:
        supported = ', '.join(sorted(METRIC_MAP))
        raise ValueError(
            f"Unsupported telemetry metric {metric!r}. Supported metrics: {supported}.",
        )
    return METRIC_MAP[key]


def _telemetry_queryset(
    machine: Machine,
    *,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> QuerySet[TelemetrySnapshot]:
    snapshots = TelemetrySnapshot.objects.filter(machine=machine)
    if from_ts is not None:
        snapshots = snapshots.filter(timestamp__gte=from_ts)
    if to_ts is not None:
        snapshots = snapshots.filter(timestamp__lte=to_ts)
    return snapshots


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def query_telemetry(
    machine: Machine,
    *,
    metric: str = 'temperature',
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    field_name, unit = _resolve_metric(metric)
    snapshots = _telemetry_queryset(
        machine,
        from_ts=from_ts,
        to_ts=to_ts,
    ).order_by('-timestamp')[:limit]
    return [
        {
            'ts': snapshot.timestamp,
            'metric': metric,
            'value': float(getattr(snapshot, field_name)),
            'unit': unit,
            'operational_status': snapshot.operational_status,
        }
        for snapshot in snapshots
    ]


def query_telemetry_aggregates(
    machine: Machine,
    *,
    metric: str = 'temperature',
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> dict:
    """Reduce a metric over every snapshot in the scoped time window (no limit)."""
    field_name, unit = _resolve_metric(metric)
    snapshots = _telemetry_queryset(
        machine,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    stats = snapshots.aggregate(
        count=Count(field_name),
        min=Min(field_name),
        max=Max(field_name),
        avg=Avg(field_name),
        sum=Sum(field_name),
    )
    operational_statuses = sorted(
        snapshots.values_list('operational_status', flat=True).distinct(),
    )
    return {
        'metric': metric,
        'unit': unit,
        'count': stats['count'],
        'min': _as_float(stats['min']),
        'max': _as_float(stats['max']),
        'avg': _as_float(stats['avg']),
        'sum': _as_float(stats['sum']),
        'operational_statuses': operational_statuses,
    }
