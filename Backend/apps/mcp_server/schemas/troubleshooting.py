"""Schemas for troubleshooting / error-code lookup (Troubleshooting Agent)."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import ScopedContext


class ListAlarmsInput(ScopedContext):
    active_only: bool = Field(
        default=True,
        description="If true (default), only 'Open'/'Acknowledged' alarms; if false, full alarm history.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class AlarmRecord(BaseModel):
    alarm_id: str
    timestamp: datetime
    alarm_code: str
    severity: str
    alarm_status: str


class ListAlarmsOutput(BaseModel):
    alarms: list[AlarmRecord]


class SearchErrorCodesInput(ScopedContext):
    query: str = Field(
        ...,
        min_length=1,
        description='Error code, alarm text, or symptom description.',
    )
    top_k: int = Field(default=5, ge=1, le=20)


class ErrorCodeHit(BaseModel):
    title: str
    summary: str
    machine_specific: bool = True


class SearchErrorCodesOutput(BaseModel):
    query: str
    hits: list[ErrorCodeHit]
