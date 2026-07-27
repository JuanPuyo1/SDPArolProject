"""Schemas for service tickets (Service Agent)."""

from typing import Literal

from pydantic import BaseModel, Field

from .common import ScopedContext


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
