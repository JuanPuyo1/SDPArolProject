"""Schemas for service tickets (Service Agent)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from .common import ScopedContext


class ListMaintenanceTicketsInput(ScopedContext):
    status: str | None = Field(
        default=None,
        description="Optional filter, e.g. 'Open', 'In progress', 'Resolved', 'Closed', 'Waiting for parts'.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class MaintenanceTicketRecord(BaseModel):
    ticket_id: str
    ticket_type: str
    ticket_status: str
    priority: str
    created_date: date
    owner_role: str
    alarm_id: str | None = None


class ListMaintenanceTicketsOutput(BaseModel):
    tickets: list[MaintenanceTicketRecord]


class CreateTicketInput(ScopedContext):
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    category: Literal['support', 'maintenance', 'spare_parts', 'other'] = 'support'


class CreateTicketOutput(BaseModel):
    stub: bool = True
    ticket_id: str
    subject: str
    priority: str
    status: str = 'open'
    note: str = 'create_ticket is a stub; no persistence yet.'
