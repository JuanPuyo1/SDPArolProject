"""
Troubleshooting & Service agent — LangChain tool-calling adapter.

Diagnoses alarms/symptoms and opens service tickets by calling MCP tools
(real tenant scoping), streaming step + tool + token chunks for the
thinking-chain UI. Same structure as OrdersBusinessAgent: one system prompt,
one tool set, one loop — the LLM decides which tools it needs rather than
Python pre-branching on regex-classified intent.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool

from apps.agents.agent_kit import AgentTool, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.mcp_server import registry

SYSTEM_PROMPT = """You are the Troubleshooting & Service agent for AROL's \
customer platform, covering industrial capping/filling machines. You \
diagnose alarms, faults, and breakdowns, and you open field-support tickets \
when the user needs a technician. You do NOT handle quotes, orders, \
contracts, or general manual/documentation lookups — if asked about those, \
say that's handled by a different agent rather than guessing. Always call \
a tool to fetch real data before answering — never invent error codes, \
telemetry readings, or ticket IDs. Only call create_ticket when the user is \
actually asking for a technician/field support, not for a diagnosis alone. \
Keep answers concise and cite error codes or ticket IDs so the frontend can \
link to them."""


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    scope = {'customer_id': customer_id, 'machine_serial': machine_serial}

    @tool
    def search_error_codes(query: str) -> dict:
        """Look up error codes / alarms and recommended troubleshooting steps.
        query: the error code, alarm text, or symptom description."""
        return registry.invoke('search_error_codes', {**scope, 'query': query})

    @tool
    def query_telemetry(metric: str) -> dict:
        """Query recent telemetry points for a metric on the scoped machine,
        e.g. cycle_count, temperature, pressure."""
        return registry.invoke('query_telemetry', {**scope, 'metric': metric})

    @tool
    def create_ticket(
        subject: str,
        description: str,
        priority: str = 'medium',
        category: str = 'support',
    ) -> dict:
        """Open a field-support/service ticket for the scoped machine. Only
        call this when the user explicitly wants a technician or field
        service, not for a diagnosis alone.
        priority: one of low, medium, high, critical.
        category: one of support, maintenance, spare_parts, other."""
        return registry.invoke(
            'create_ticket',
            {
                **scope,
                'subject': subject,
                'description': description,
                'priority': priority,
                'category': category,
            },
        )

    return [
        AgentTool(search_error_codes, 'Searching error codes and recommended actions…'),
        AgentTool(query_telemetry, 'Querying recent telemetry readings…'),
        AgentTool(create_ticket, 'Opening field-support ticket…'),
    ]


class TroubleshootingServiceAgent:
    AGENT_ID = 'troubleshooting_service'

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

        user_message = message
        if attachments:
            names = ', '.join(a.filename for a in attachments)
            user_message += (
                f'\n\n[The user attached {len(attachments)} file(s): {names}. '
                'Attachment analysis is not wired yet — acknowledge receipt only.]'
            )

        yield from run_tool_calling_loop(
            active_llm,
            tools,
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            history=history,
            new_messages_sink=new_messages_sink,
        )
