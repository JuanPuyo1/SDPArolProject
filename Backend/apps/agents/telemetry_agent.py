"""
Telemetry agent — LangChain tool-calling adapter.

Queries and analyzes real-time and historical sensor telemetry points (temperature,
pressure, cycle counts, operating speed, vibration, etc.) for scoped machines
by calling MCP tools, streaming step + tool + token chunks for the
thinking-chain UI.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import BaseMessage

from apps.agents.agent_kit import (
    AgentTool,
    build_agent_tools,
    build_llm,
    load_machine_context,
    run_tool_calling_loop,
)
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk

SYSTEM_PROMPT = """You are the Telemetry agent for AROL's customer platform, \
covering industrial capping/filling machines. You answer questions about \
machine sensor metrics, historical telemetry readings, cycle counts, \
temperature, pressure, vibration, and operational performance trends. \
You do NOT handle quotes, orders, contracts, manual lookups, or opening service \
tickets. Always call a tool to fetch real telemetry data before \
answering — never invent sensor values, units, or timestamps. Keep answers \
concise and cite metric names, values, units, and timestamps so the frontend can display them clearly."""

_STEP_LABELS = {'query_telemetry': 'Querying machine telemetry metrics…'}


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    return build_agent_tools(
        'telemetry',
        customer_id=customer_id,
        machine_serial=machine_serial,
        step_labels=_STEP_LABELS,
    )


class TelemetryAgent:
    AGENT_ID = 'telemetry'

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
        emit_tokens: bool = True,
        answer_sink: list[str] | None = None,
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
            machine_context=machine_ctx[0],
            emit_tokens=emit_tokens,
            answer_sink=answer_sink
        )
