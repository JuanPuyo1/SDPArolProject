"""
Manuals agent — LangChain tool-calling adapter.

Answers how-to/operating/maintenance questions by searching the machine's
use-and-maintenance manual and technical documentation (RAG-backed via
apps.mcp_server.rag_engine, behind the search_manual MCP tool), streaming
step + tool + token chunks for the thinking-chain UI. Same structure as the
other two agents: one system prompt, one tool, one loop.
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import BaseMessage

from apps.agents.agent_kit import AgentTool, build_agent_tools, build_llm, load_machine_context, run_tool_calling_loop
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk

_STEP_LABELS = {'search_manual': 'Searching manual for related procedures…'}

SYSTEM_PROMPT = """You are the Manuals agent for AROL's customer platform, \
covering industrial capping/filling machines. You answer questions about \
how to operate, adjust, or maintain a machine by searching its use-and- \
maintenance manual and technical documentation. You do NOT diagnose active \
alarms or faults, open service tickets, or handle quotes/orders/contracts — \
if asked about those, say that's handled by a different agent rather than \
guessing. Always call the search tool to fetch real passages before \
answering — never invent procedures, page numbers, or manual content. Keep \
answers concise and cite the page number/section when available so the \
frontend can link to them."""


def _build_tools(customer_id: str, machine_serial: str) -> list[AgentTool]:
    return build_agent_tools(
        'manuals',
        customer_id=customer_id,
        machine_serial=machine_serial,
        step_labels=_STEP_LABELS,
    )


class ManualsAgent:
    AGENT_ID = 'manuals'

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
            machine_context=machine_ctx[0],
        )
