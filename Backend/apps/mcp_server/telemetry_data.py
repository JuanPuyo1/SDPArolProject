"""CSV-backed sample data for Telemetry tools.

Loads IoT telemetry points from Expanded_Telemetry_Data.csv and provides pandas-based
filtering by machine serial, metric, time window, and result limits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DATA_PATH = (
    Path(__file__).resolve().parents[3]
    / 'Data'
    / 'Telemetry'
    / 'Expanded_Telemetry_Data.csv'
)

# Metric name aliases mapping to CSV column name and unit
METRIC_MAP: dict[str, tuple[str, str | None]] = {
    'temperature': ('Motor_Temperature_C', '°C'),
    'motor_temperature': ('Motor_Temperature_C', '°C'),
    'motor_temperature_c': ('Motor_Temperature_C', '°C'),
    'temp': ('Motor_Temperature_C', '°C'),
    'speed': ('Production_Speed_BPH', 'BPH'),
    'operating_speed': ('Production_Speed_BPH', 'BPH'),
    'production_speed': ('Production_Speed_BPH', 'BPH'),
    'production_speed_bph': ('Production_Speed_BPH', 'BPH'),
    'cycle_count': ('Production_Speed_BPH', 'BPH'),
    'cycle': ('Production_Speed_BPH', 'BPH'),
    'cycles': ('Production_Speed_BPH', 'BPH'),
    'torque': ('Capping_Torque_Nm', 'Nm'),
    'capping_torque': ('Capping_Torque_Nm', 'Nm'),
    'capping_torque_nm': ('Capping_Torque_Nm', 'Nm'),
    'top_load': ('Top_Load_N', 'N'),
    'load': ('Top_Load_N', 'N'),
    'pressure': ('Top_Load_N', 'N'),
    'top_load_n': ('Top_Load_N', 'N'),
    'vibration': ('Vibration_Level_mm_s', 'mm/s'),
    'vibration_level': ('Vibration_Level_mm_s', 'mm/s'),
    'vibration_level_mm_s': ('Vibration_Level_mm_s', 'mm/s'),
    'operating_status': ('Operating_Status', None),
    'status': ('Operating_Status', None),
    'active_fault_code': ('Active_Fault_Code', None),
    'fault_code': ('Active_Fault_Code', None),
    'fault': ('Active_Fault_Code', None),
}


class TelemetryDataStore:
    def __init__(self, csv_path: Path = DATA_PATH) -> None:
        self.csv_path = csv_path
        if csv_path.exists():
            self.df = pd.read_csv(csv_path)
            self.df['Timestamp'] = pd.to_datetime(self.df['Timestamp'])
            if self.df['Timestamp'].dt.tz is None:
                self.df['Timestamp'] = self.df['Timestamp'].dt.tz_localize(UTC)
        else:
            self.df = pd.DataFrame(
                columns=[
                    'Timestamp',
                    'Client_ID',
                    'Machine_ID',
                    'Machine_Serial',
                    'Operating_Status',
                    'Production_Speed_BPH',
                    'Capping_Torque_Nm',
                    'Top_Load_N',
                    'Vibration_Level_mm_s',
                    'Motor_Temperature_C',
                    'Active_Fault_Code',
                ]
            )

    def _resolve_metric(self, metric: str) -> tuple[str, str | None]:
        clean_metric = metric.strip().lower()
        if clean_metric in METRIC_MAP:
            return METRIC_MAP[clean_metric]

        # Check exact column names
        for col in self.df.columns:
            if col.lower() == clean_metric:
                unit = None
                if col.endswith('_C'):
                    unit = '°C'
                elif col.endswith('_Nm'):
                    unit = 'Nm'
                elif col.endswith('_N'):
                    unit = 'N'
                elif col.endswith('_mm_s'):
                    unit = 'mm/s'
                elif col.endswith('_BPH'):
                    unit = 'BPH'
                return col, unit

        # Fallback to Motor_Temperature_C
        return 'Motor_Temperature_C', '°C'

    def query_telemetry(
        self,
        *,
        customer_id: str | None = None,
        machine_serial: str | None = None,
        metric: str = 'temperature',
        from_ts: datetime | str | None = None,
        to_ts: datetime | str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        df = self.df
        if df.empty:
            return []

        # Filter by Machine_Serial first, then Machine_ID, then Client_ID
        if machine_serial:
            if 'Machine_Serial' in df.columns:
                s_filtered = df[df['Machine_Serial'] == machine_serial]
                if not s_filtered.empty:
                    df = s_filtered
                else:
                    m_filtered = df[df['Machine_ID'] == machine_serial]
                    if not m_filtered.empty:
                        df = m_filtered
                    elif customer_id:
                        c_filtered = df[df['Client_ID'] == customer_id]
                        if not c_filtered.empty:
                            df = c_filtered
            else:
                m_filtered = df[df['Machine_ID'] == machine_serial]
                if not m_filtered.empty:
                    df = m_filtered
                elif customer_id:
                    c_filtered = df[df['Client_ID'] == customer_id]
                    if not c_filtered.empty:
                        df = c_filtered

        # Time range filtering
        if from_ts:
            if isinstance(from_ts, str):
                from_dt = pd.to_datetime(from_ts)
            else:
                from_dt = pd.to_datetime(from_ts)
            if from_dt.tzinfo is None:
                from_dt = from_dt.tz_localize(UTC)
            df = df[df['Timestamp'] >= from_dt]

        if to_ts:
            if isinstance(to_ts, str):
                to_dt = pd.to_datetime(to_ts)
            else:
                to_dt = pd.to_datetime(to_ts)
            if to_dt.tzinfo is None:
                to_dt = to_dt.tz_localize(UTC)
            df = df[df['Timestamp'] <= to_dt]

        col_name, unit = self._resolve_metric(metric)

        # Ensure column exists
        if col_name not in df.columns:
            col_name = 'Motor_Temperature_C'
            unit = '°C'

        # Sort latest timestamps first (or chronological)
        df_sorted = df.sort_values('Timestamp', ascending=False)
        subset = df_sorted.head(limit)

        records: list[dict[str, Any]] = []
        for _, row in subset.iterrows():
            raw_val = row[col_name]
            try:
                val = float(raw_val) if pd.notna(raw_val) else 0.0
            except (ValueError, TypeError):
                val = 0.0

            ts_val = row['Timestamp']
            if isinstance(ts_val, pd.Timestamp):
                ts_dt = ts_val.to_pydatetime()
            else:
                ts_dt = datetime.now(tz=UTC)

            records.append(
                {
                    'ts': ts_dt,
                    'metric': metric,
                    'value': val,
                    'unit': unit,
                }
            )

        return records


@lru_cache(maxsize=1)
def get_store() -> TelemetryDataStore:
    return TelemetryDataStore()
