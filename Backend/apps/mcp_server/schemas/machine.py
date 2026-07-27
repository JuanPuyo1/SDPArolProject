"""Schemas for machine lookup tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .common import ScopedContext


class GetMachineInfoInput(ScopedContext):
    """Fetch full machine record for the scoped customer + serial."""


class ListCustomerMachinesInput(BaseModel):
    """List machines owned by a customer (no single-machine scope required)."""

    customer_id: str = Field(
        ...,
        min_length=1,
        description='Tenant identity: Django username or numeric user id as string.',
    )


class MachineSummary(BaseModel):
    id: int
    serial_number: str
    model: str
    full_model: str
    manufacturing_year: int


class GetMachineInfoOutput(BaseModel):
    machine: dict[str, Any] = Field(
        ...,
        description='Full machine payload (same shape as REST /api/machines/<serial>/).',
    )


class ListCustomerMachinesOutput(BaseModel):
    machines: list[MachineSummary]
