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

from apps.agents.agent_kit import AgentTool, build_agent_tools, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk

# The two registry.py domains this agent currently merges into one; split
# them out here (not by retagging the registry) if Service ever becomes its
# own agent.
_OWNED_AGENT_TAGS = {'troubleshooting', 'service'}

# Registry.py owns each tool's name/description/schema; this only supplies
# the UI-facing progress label shown while it runs.
_STEP_LABELS = {
    'search_error_codes': 'Searching error codes and recommended actions…',
    'list_alarms': 'Checking alarm history…',
    'create_ticket': 'Opening field-support ticket…',
    'list_maintenance_tickets': 'Checking ticket history…',
}

SYSTEM_PROMPT = """You are the Troubleshooting & Service agent for AROL's \
customer platform, covering industrial capping/filling machines. You \
diagnose alarms, faults, and breakdowns using the machine's real alarm \
history, and you open or look up field-support tickets when the user needs \
a technician. You do NOT handle quotes, orders, contracts, telemetry trend \
questions, or general manual/documentation lookups — if asked about those, \
say that's handled by a different agent rather than guessing. Always call \
a tool to fetch real data before answering — never invent error codes, \
alarm codes, or ticket IDs. Only call create_ticket when the user is \
actually asking for a technician/field support, not for a diagnosis alone; \
use list_maintenance_tickets first to check whether a relevant ticket \
already exists. Keep answers concise and cite alarm codes or ticket IDs so \
the frontend can link to them."""


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    return build_agent_tools(
        _OWNED_AGENT_TAGS,
        customer_id=customer_id,
        machine_serial=machine_serial,
        step_labels=_STEP_LABELS,
    )


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
