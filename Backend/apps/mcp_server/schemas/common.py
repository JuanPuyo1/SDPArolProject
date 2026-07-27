"""Shared MCP schema primitives."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class ScopedContext(BaseModel):
    """
    Every tenant-scoped tool requires these two fields.

    Orchestrators MUST pass them on every tool call (except pure debug tools
    like ``echo``). Tools re-validate ownership before touching data.
    """

    customer_id: str = Field(
        ...,
        min_length=1,
        description='Tenant identity: Django username or numeric user id as string.',
    )
    machine_serial: str = Field(
        ...,
        min_length=1,
        description='Active machine serial number (e.g. A3279).',
    )


class ToolError(BaseModel):
    status: Literal['error'] = 'error'
    message: str
    code: str | None = Field(
        default=None,
        description='Optional machine-readable error code (e.g. NOT_FOUND, FORBIDDEN).',
    )


class ToolResponse(BaseModel, Generic[T]):
    """Envelope used by the registry for successful tool results."""

    status: Literal['ok'] = 'ok'
    data: T
