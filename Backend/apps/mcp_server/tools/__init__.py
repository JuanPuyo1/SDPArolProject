"""MCP tool implementations."""

from .create_ticket import create_ticket
from .echo import echo
from .get_contract_info import get_contract_info
from .get_machine_info import get_machine_info
from .get_order_status import get_order_status
from .get_quote_history import get_quote_history
from .list_customer_machines import list_customer_machines
from .list_spare_parts import list_spare_parts
from .query_telemetry import query_telemetry
from .search_manual import search_manual

__all__ = [
    'echo',
    'get_machine_info',
    'list_customer_machines',
    'search_manual',
    'query_telemetry',
    'create_ticket',
    'list_spare_parts',
    'get_quote_history',
    'get_order_status',
    'get_contract_info',
]
