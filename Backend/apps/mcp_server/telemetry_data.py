"""ORM-backed data access for telemetry queries (Telemetry Agent).

Reads real TelemetrySnapshot rows (apps.machines.models) for a scoped
machine. Only numeric snapshot fields are exposed as queryable "metrics" --
QueryTelemetryOutput's TelemetryPoint.value is a float, so non-numeric
fields (operational_status, health_note) aren't reachable through here.
"""

from __future__ import annotations

from datetime import datetime

from apps.machines.models import Machine, TelemetrySnapshot

# metric alias -> (TelemetrySnapshot field name, unit)
METRIC_MAP: dict[str, tuple[str, str | None]] = {
    'temperature': ('temperature_c', '°C'),
    'motor_temperature': ('temperature_c', '°C'),
    'temperature_c': ('temperature_c', '°C'),
    'temp': ('temperature_c', '°C'),
    'production_rate': ('production_rate_bph', 'BPH'),
    'production_rate_bph': ('production_rate_bph', 'BPH'),
    'speed': ('production_rate_bph', 'BPH'),
    'operating_speed': ('production_rate_bph', 'BPH'),
    'cycle_count': ('production_rate_bph', 'BPH'),
    'cycle': ('production_rate_bph', 'BPH'),
    'uptime': ('uptime_percentage', '%'),
    'uptime_percentage': ('uptime_percentage', '%'),
    'alarm_count': ('alarm_count', 'count'),
    'alarms': ('alarm_count', 'count'),
    'energy': ('energy_kwh', 'kWh'),
    'energy_kwh': ('energy_kwh', 'kWh'),
    'power': ('energy_kwh', 'kWh'),
}
_DEFAULT_METRIC = ('temperature_c', '°C')


def _resolve_metric(metric: str) -> tuple[str, str | None]:
    return METRIC_MAP.get(metric.strip().lower(), _DEFAULT_METRIC)


def query_telemetry(
    machine: Machine,
    *,
    metric: str = 'temperature',
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    field_name, unit = _resolve_metric(metric)
    snapshots = TelemetrySnapshot.objects.filter(machine=machine)
    if from_ts is not None:
        snapshots = snapshots.filter(timestamp__gte=from_ts)
    if to_ts is not None:
        snapshots = snapshots.filter(timestamp__lte=to_ts)
    snapshots = snapshots.order_by('-timestamp')[:limit]
    return [
        {
            'ts': snapshot.timestamp,
            'metric': metric,
            'value': float(getattr(snapshot, field_name)),
            'unit': unit,
        }
        for snapshot in snapshots
    ]
