"""get_quote_history — quote revision history stub for Orders/Business Agent."""

from apps.mcp_server.orders_data import get_store
from apps.mcp_server.schemas.orders import QuoteHistoryInput, QuoteHistoryOutput, QuoteRevision
from apps.mcp_server.scoping import get_owned_machine


def get_quote_history(params: QuoteHistoryInput) -> QuoteHistoryOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    rows = get_store().quote_history(quote_id=params.quote_id)
    return QuoteHistoryOutput(revisions=[QuoteRevision(**row) for row in rows])
