"""Schemas for quote/order/contract lookups (Orders/Business Agent)."""

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
    stub: bool = True
    revisions: list[QuoteRevision]
    note: str = 'get_quote_history returns representative sample data until the quoting system is connected.'


class OrderStatusInput(ScopedContext):
    """No extra filters — orders are always scoped to the caller's customer + machine."""


class OrderRecord(BaseModel):
    order_id: str
    quote_id: str | None = None
    order_date: str
    status: str
    item_summary: str
    amount_eur: float


class OrderStatusOutput(BaseModel):
    stub: bool = True
    orders: list[OrderRecord]
    note: str = 'get_order_status returns representative sample data until the ERP system is connected.'


class ContractInfoInput(ScopedContext):
    """No extra filters — contracts are always scoped to the caller's customer + machine."""


class ContractRecord(BaseModel):
    contract_id: str
    type: str
    start_date: str
    end_date: str


class ContractInfoOutput(BaseModel):
    stub: bool = True
    contracts: list[ContractRecord]
    note: str = 'get_contract_info returns representative sample data until the contracts system is connected.'
