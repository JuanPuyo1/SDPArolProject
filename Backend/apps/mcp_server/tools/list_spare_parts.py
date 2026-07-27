"""list_spare_parts — commerce catalog stub for Business Agent."""

from apps.mcp_server.schemas.business import (
    ListSparePartsInput,
    ListSparePartsOutput,
    SparePartItem,
)
from apps.mcp_server.scoping import get_owned_machine


def list_spare_parts(params: ListSparePartsInput) -> ListSparePartsOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    parts = [
        SparePartItem(
            part_number='STUB-PART-001',
            name=f'Stub part matching {params.query!r}',
            unit_code=None,
            description=(
                f'Catalog not connected. Machine {machine.serial_number} '
                f'({machine.model}).'
            ),
            availability='unknown',
        )
    ][: params.limit]
    return ListSparePartsOutput(query=params.query, parts=parts)
