"""
Fleet agent — LangChain tool-calling adapter for the general, company-scoped
chatbot (as opposed to every other agent in this package, which is hard-locked
to one machine).

Answers catalog/directory questions about the caller's own company: which
machines it owns, machine model specs, the company profile, and who else at
the company uses the platform. Does NOT load machine context and does NOT
accept a machine_serial -- see fleet_orchestrator.py for how this agent is
invoked outside the per-machine graph.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import BaseMessage

from apps.agents.agent_kit import (
    AgentTool,
    build_agent_tools,
    build_llm,
    mcp_tool,
    run_tool_calling_loop,
)
from apps.agents.ports import OrchestratorChunk

SYSTEM_PROMPT = """You are the general Fleet Information agent for AROL's \
customer platform, covering industrial capping/filling machines. You answer \
general questions about the caller's own company account: which machines the \
company owns (serial numbers, models, plants), machine model specs \
(container type, cap type, industry segment, head count, primitive \
diameter), the company's own profile (name, country, sector, city), and who \
else at the company uses this platform (username, job title, role).

You do NOT handle alarms, telemetry, maintenance tickets, quotes, orders, or \
manual/troubleshooting lookups for any specific machine -- if asked, say \
plainly that those questions belong in the machine-specific chat assistant \
(available once a machine is selected), and do not attempt to answer them \
yourself.

Always call a tool to fetch real data before answering -- never invent \
machine, model, company, or user details. When listing machines or \
teammates, present them clearly (e.g. as a short list) rather than a wall of \
text."""

_STEP_LABELS = {
    'list_customer_machines': 'Listing your company machines…',
    'get_company_info': 'Loading company profile…',
    'list_company_users': 'Loading company directory…',
}


def _build_tools(customer_id: str) -> list[AgentTool]:
    return [
        mcp_tool(
            'list_customer_machines',
            customer_id=customer_id,
            machine_serial='',
            step_label=_STEP_LABELS['list_customer_machines'],
        ),
        *build_agent_tools(
            'fleet',
            customer_id=customer_id,
            machine_serial='',
            step_labels=_STEP_LABELS,
        ),
    ]


class FleetAgent:
    AGENT_ID = 'fleet'

    def run(
        self,
        *,
        customer_id: str,
        message: str,
        history: list[BaseMessage] | None = None,
        new_messages_sink: list[BaseMessage] | None = None,
        llm=None,
        emit_tokens: bool = True,
        answer_sink: list[str] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        tools = _build_tools(customer_id)
        active_llm = llm or build_llm([t.tool for t in tools])

        yield from run_tool_calling_loop(
            active_llm,
            tools,
            system_prompt=SYSTEM_PROMPT,
            user_message=message,
            history=history,
            new_messages_sink=new_messages_sink,
            emit_tokens=emit_tokens,
            answer_sink=answer_sink,
        )
