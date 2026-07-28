"""get_order_status — confirmed order status stub for Orders/Business Agent."""

from apps.mcp_server.orders_data import get_store
from apps.mcp_server.schemas.orders import OrderRecord, OrderStatusInput, OrderStatusOutput
from apps.mcp_server.scoping import get_owned_machine


def get_order_status(params: OrderStatusInput) -> OrderStatusOutput:
    get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    rows = get_store().order_status()
    return OrderStatusOutput(orders=[OrderRecord(**row) for row in rows])
