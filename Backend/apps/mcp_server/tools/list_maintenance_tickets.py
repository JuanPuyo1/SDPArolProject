"""list_maintenance_tickets — real ticket history for the scoped machine (Service Agent)."""

from apps.machines.models import MaintenanceTicket
from apps.mcp_server.schemas.ticket import (
    ListMaintenanceTicketsInput,
    ListMaintenanceTicketsOutput,
    MaintenanceTicketRecord,
)
from apps.mcp_server.scoping import get_owned_machine


def list_maintenance_tickets(params: ListMaintenanceTicketsInput) -> ListMaintenanceTicketsOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    tickets = MaintenanceTicket.objects.filter(machine=machine)
    if params.status:
        tickets = tickets.filter(ticket_status__iexact=params.status)
    tickets = tickets.order_by('-created_date')[: params.limit]
    return ListMaintenanceTicketsOutput(
        tickets=[
            MaintenanceTicketRecord(
                ticket_id=ticket.ticket_id,
                ticket_type=ticket.ticket_type,
                ticket_status=ticket.ticket_status,
                priority=ticket.priority,
                created_date=ticket.created_date,
                owner_role=ticket.owner_role,
                alarm_id=ticket.alarm_id,
            )
            for ticket in tickets
        ]
    )
