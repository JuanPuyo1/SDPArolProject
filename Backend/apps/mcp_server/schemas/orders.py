"""Schemas for quote/order lookups (Orders/Business Agent), ORM-backed."""

from pydantic import BaseModel, Field

from .common import ScopedContext


class QuoteHistoryInput(ScopedContext):
    quote_id: str | None = Field(
        default=None,
        description='Optional specific quote_id to filter to (e.g. QUO-001).',
    )


class QuoteRevision(BaseModel):
    quote_id: str
    revision_number: int
    quote_date: str
    status: str
    item_summary: str
    amount_eur: float


class QuoteHistoryOutput(BaseModel):
    revisions: list[QuoteRevision]


class OrderStatusInput(ScopedContext):
    """No extra filters — orders are always scoped to the caller's customer + machine."""


class OrderLineRecord(BaseModel):
    order_line_id: str
    fulfillment_status: str


class OrderRecord(BaseModel):
    order_id: str
    quote_id: str | None = None
    order_date: str
    expected_delivery_date: str | None = None
    status: str
    shipment_status: str | None = None
    currency: str = 'EUR'
    notes: str = ''
    item_summary: str
    amount_eur: float
    order_lines: list[OrderLineRecord] = Field(default_factory=list)



class OrderStatusOutput(BaseModel):
    orders: list[OrderRecord]

