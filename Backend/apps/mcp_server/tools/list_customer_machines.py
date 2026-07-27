"""list_customer_machines — fleet summary for one tenant."""

from apps.machines.models import Machine
from apps.mcp_server.schemas.machine import (
    ListCustomerMachinesInput,
    ListCustomerMachinesOutput,
    MachineSummary,
)
from apps.mcp_server.scoping import resolve_customer


def list_customer_machines(params: ListCustomerMachinesInput) -> ListCustomerMachinesOutput:
    user = resolve_customer(params.customer_id)
    qs = Machine.objects.filter(owner=user).order_by('serial_number')
    machines = [
        MachineSummary(
            id=m.pk,
            serial_number=m.serial_number,
            model=m.model,
            full_model=m.full_model,
            manufacturing_year=m.manufacturing_year,
        )
        for m in qs
    ]
    return ListCustomerMachinesOutput(machines=machines)
