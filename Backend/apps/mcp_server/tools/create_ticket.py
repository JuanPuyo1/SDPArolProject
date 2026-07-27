"""create_ticket — service ticket stub for Service Agent."""

import uuid

from apps.mcp_server.schemas.ticket import CreateTicketInput, CreateTicketOutput
from apps.mcp_server.scoping import get_owned_machine


def create_ticket(params: CreateTicketInput) -> CreateTicketOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    ticket_id = f'TKT-{uuid.uuid4().hex[:8].upper()}'
    return CreateTicketOutput(
        ticket_id=ticket_id,
        subject=params.subject,
        priority=params.priority,
        status='open',
    )
