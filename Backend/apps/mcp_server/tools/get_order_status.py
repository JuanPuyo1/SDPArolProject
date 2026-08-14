"""get_order_status — confirmed order status for Orders/Business Agent, backed by the ORM."""

from apps.mcp_server import orders_data
from apps.mcp_server.schemas.orders import OrderRecord, OrderStatusInput, OrderStatusOutput
from apps.mcp_server.scoping import get_owned_machine


def get_order_status(params: OrderStatusInput) -> OrderStatusOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    rows = orders_data.order_status(machine.company)
    return OrderStatusOutput(orders=[OrderRecord(**row) for row in rows])
