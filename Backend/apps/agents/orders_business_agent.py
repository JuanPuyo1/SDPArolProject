"""
Orders/Business agent — LangChain tool-calling adapter.

Answers quote-history, order-status, and contract questions by calling MCP
business tools (real tenant scoping, sample data until the quoting/ERP/
contracts systems are connected), streaming step + tool + token chunks for
the thinking-chain UI.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.tools import tool

from apps.agents.agent_kit import AgentTool, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.mcp_server import registry

SYSTEM_PROMPT = """You are the Orders/Business agent for AROL's customer \
platform. You answer questions about quotes (including revision history), \
order status, and contracts for industrial capping/filling machines. You \
do NOT handle service tickets or troubleshooting — if asked about a machine \
fault, breakdown, or open service ticket, say that's handled by a different \
agent rather than guessing. Always call a tool to fetch real data before \
answering — never invent quote/order numbers, dates, or statuses. Keep \
answers concise and cite the relevant quote/order/contract IDs so the \
frontend can link to them."""


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    scope = {'customer_id': customer_id, 'machine_serial': machine_serial}

    @tool
    def get_quote_history(quote_id: str | None = None) -> dict:
        """Look up the full quote history (all revisions, oldest to newest) for
        the scoped machine, optionally filtered to one quote_id. Use this for
        questions about quote status, price changes across revisions, or
        whether a quote was accepted/rejected."""
        return registry.invoke('get_quote_history', {**scope, 'quote_id': quote_id})

    @tool
    def get_order_status() -> dict:
        """Look up confirmed order status and amount for the scoped machine.
        Orders may reference a quote_id if they originated from an accepted
        quote."""
        return registry.invoke('get_order_status', scope)

    @tool
    def get_contract_info() -> dict:
        """Look up warranty/maintenance contract details (type, start/end
        dates) for the scoped machine."""
        return registry.invoke('get_contract_info', scope)

    return [
        AgentTool(get_quote_history, 'Looking up quote history…'),
        AgentTool(get_order_status, 'Checking order status…'),
        AgentTool(get_contract_info, 'Checking contract details…'),
    ]


class OrdersBusinessAgent:
    AGENT_ID = 'orders_business'

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
        llm=None,
    ) -> Iterator[OrchestratorChunk]:
        machine_ctx: list[dict] = []
        yield from load_machine_context(customer_id, machine_serial, machine_ctx)
        if machine_ctx[0]['status'] != 'ok':
            yield OrchestratorChunk(
                type='error',
                message=machine_ctx[0].get('message', 'Machine lookup failed.'),
            )
            return

        tools = _build_tools(customer_id, machine_serial)
        active_llm = llm or build_llm([t.tool for t in tools])

        yield from run_tool_calling_loop(
            active_llm,
            tools,
            system_prompt=SYSTEM_PROMPT,
            user_message=message,
        )
