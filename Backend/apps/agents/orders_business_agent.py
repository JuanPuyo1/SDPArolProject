"""
Orders/Business agent — LangChain tool-calling adapter.

Answers quote-history, order-status, and spare-parts questions by calling
MCP business tools (real tenant scoping; quotes/orders are ORM-backed, spare
parts are still sample data until the catalog system is connected),
streaming step + tool + token chunks for the thinking-chain UI.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import BaseMessage

from apps.agents.agent_kit import AgentTool, build_agent_tools, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk

SYSTEM_PROMPT = """You are the Orders/Business agent for AROL's customer \
platform. You answer questions about quotes (including revision history), \
order status, and spare parts for industrial capping/filling machines. \
You do NOT handle service tickets, troubleshooting, or contract/warranty \
lookups — if asked about a machine fault, breakdown, open service ticket, \
or contract details, say that's handled by a different agent rather than \
guessing. Always call a tool to fetch real data before answering — never \
invent quote/order numbers, dates, statuses, or part numbers. Keep answers \
concise and cite the relevant quote/order/part IDs so the frontend can \
link to them."""

# Registry.py owns each tool's name/description/schema; this only supplies
# the UI-facing progress label shown while it runs (not duplicated data --
# there's no other copy of this text to drift from).
_STEP_LABELS = {
    'get_quote_history': 'Looking up quote history…',
    'get_order_status': 'Checking order status…',
    'list_spare_parts': 'Looking up spare parts…',
}


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    return build_agent_tools(
        'business',
        customer_id=customer_id,
        machine_serial=machine_serial,
        step_labels=_STEP_LABELS,
    )


class OrdersBusinessAgent:
    AGENT_ID = 'orders_business'

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
        history: list[BaseMessage] | None = None,
        new_messages_sink: list[BaseMessage] | None = None,
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
            history=history,
            new_messages_sink=new_messages_sink,
        )
