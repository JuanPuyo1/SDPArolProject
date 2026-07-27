"""get_machine_info — full machine record for scoped customer + serial."""

from apps.machines.serializers import machine_to_dict
from apps.mcp_server.schemas.machine import GetMachineInfoInput, GetMachineInfoOutput
from apps.mcp_server.scoping import get_owned_machine


def get_machine_info(params: GetMachineInfoInput) -> GetMachineInfoOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    return GetMachineInfoOutput(machine=machine_to_dict(machine))
