"""get_contract_info — warranty/maintenance contract stub for Orders/Business Agent."""

from apps.mcp_server.orders_data import get_store
from apps.mcp_server.schemas.orders import ContractInfoInput, ContractInfoOutput, ContractRecord
from apps.mcp_server.scoping import get_owned_machine


def get_contract_info(params: ContractInfoInput) -> ContractInfoOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    rows = get_store().contract_info()
    return ContractInfoOutput(contracts=[ContractRecord(**row) for row in rows])
