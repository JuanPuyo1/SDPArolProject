"""
Telemetry agent — LangChain tool-calling adapter.

Queries and analyzes historical sensor telemetry points (temperature,
production rate/operating speed, uptime, alarm count, energy consumption)
for scoped machines by calling MCP tools, streaming step + tool + token
chunks for the thinking-chain UI. Pressure, vibration, and per-cycle counts
are NOT in the data model -- do not add them back to the prompt below
without first adding the underlying TelemetrySnapshot field and
telemetry_data.METRIC_MAP entry, or query_telemetry will have nothing real
to return for them.
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
machine sensor metrics and historical telemetry readings -- temperature, \
production rate / operating speed, uptime percentage, alarm count, and \
energy consumption. You do NOT handle quotes, orders, contracts, manual \
lookups, or opening service tickets, and you have no data for pressure, \
vibration, or per-cycle counts -- say plainly that a metric isn't tracked \
rather than guessing or substituting a different one. Always call a tool to \
fetch real telemetry data before answering — never invent sensor values, \
units, or timestamps. Keep answers concise and cite metric names, values, \
units, and timestamps so the frontend can display them clearly.

Every telemetry point also carries the machine's operational_status at that \
moment (Running, Idle, Stopped, Alarm, Maintenance, or Size change). When \
the user asks for an average, minimum, maximum, total, or count over a time \
window, call query_telemetry with include_aggregates=true (and \
include_points=false unless they also want the raw series). Use the tool's \
aggregates field for those numbers — never compute statistics yourself from \
raw points. When you report an aggregate, note the operational_statuses \
returned alongside it; a statistic mixing Running periods with Stopped/Alarm/ \
Maintenance periods can be misleading without that context."""

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
