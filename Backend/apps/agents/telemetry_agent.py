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
from langchain_core.tools import tool

from apps.agents.agent_kit import AgentTool, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.mcp_server import registry

SYSTEM_PROMPT = """You are the Telemetry agent for AROL's customer platform, \
covering industrial capping/filling machines. You answer questions about \
machine sensor metrics, historical telemetry readings, cycle counts, \
temperature, pressure, vibration, and operational performance trends. \
You do NOT handle quotes, orders, contracts, manual lookups, or opening service \
tickets. Always call a tool to fetch real telemetry data before \
answering — never invent sensor values, units, or timestamps. Keep answers \
concise and cite metric names, values, units, and timestamps so the frontend can display them clearly."""


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    scope = {'customer_id': customer_id, 'machine_serial': machine_serial}

    @tool
    def query_telemetry(
        metric: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Query telemetry points for a specific metric on the scoped machine.
        metric: metric name, e.g. cycle_count, temperature, pressure, operating_speed.
        from_ts: optional start of time window in ISO-8601 format.
        to_ts: optional end of time window in ISO-8601 format.
        limit: maximum number of telemetry points to return (default 50)."""
        payload: dict = {**scope, 'metric': metric, 'limit': limit}
        if from_ts is not None:
            payload['from_ts'] = from_ts
        if to_ts is not None:
            payload['to_ts'] = to_ts
        return registry.invoke('query_telemetry', payload)

    return [
        AgentTool(query_telemetry, 'Querying machine telemetry metrics…'),
    ]


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
            emit_tokens=emit_tokens,
            answer_sink=answer_sink
        )
