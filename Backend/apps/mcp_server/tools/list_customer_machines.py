"""list_customer_machines — fleet summary for one tenant."""

from apps.machines.models import Machine
from apps.mcp_server.schemas.machine import (
    ListCustomerMachinesInput,
    ListCustomerMachinesOutput,
    MachineSummary,
)
from apps.mcp_server.scoping import ScopeError, resolve_customer


def list_customer_machines(params: ListCustomerMachinesInput) -> ListCustomerMachinesOutput:
    user = resolve_customer(params.customer_id)
    if user.company_id is None:
        raise ScopeError('User is not assigned to a company.', code='FORBIDDEN')

    qs = (
        Machine.objects.filter(company_id=user.company_id)
        .select_related('model')
        .order_by('serial_number')
    )
    machines = [
        MachineSummary(
            id=m.pk,
            serial_number=m.serial_number,
            model=m.model.model_code,
            full_model=m.model.model_code,
            manufacturing_year=m.delivery_date.year,
        )
        for m in qs
    ]
    return ListCustomerMachinesOutput(machines=machines)
