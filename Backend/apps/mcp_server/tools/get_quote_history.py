"""get_quote_history — quote revision history for Orders/Business Agent, backed by the ORM."""

from apps.mcp_server import orders_data
from apps.mcp_server.schemas.orders import QuoteHistoryInput, QuoteHistoryOutput, QuoteRevision
from apps.mcp_server.scoping import get_owned_machine


def get_quote_history(params: QuoteHistoryInput) -> QuoteHistoryOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    rows = orders_data.quote_history(machine.company, quote_id=params.quote_id)
    return QuoteHistoryOutput(revisions=[QuoteRevision(**row) for row in rows])
