"""Shared building blocks for LangChain tool-calling agents.

Every chat agent (troubleshooting/service, orders/business, ...) follows the
same shape:

    1. load_machine_context(...)   -- real tenant scoping via MCP registry
    2. build this agent's tools, closed over customer_id/machine_serial
       (never exposed to the LLM -- the model must never supply tenant scope)
    3. run_tool_calling_loop(...)  -- the actual Claude round-trips

This module holds the parts that are identical across agents so each agent
file only has to define its system prompt and its tools.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, NamedTuple

from django.conf import settings
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from apps.agents.ports import OrchestratorChunk
from apps.mcp_server import registry

DEFAULT_MODEL = getattr(settings, 'ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')


class AgentTool(NamedTuple):
    """A LangChain tool paired with the `step` chunk label shown while it runs."""

    tool: BaseTool
    step_label: str


def build_llm(tools: list[BaseTool], *, model: str = DEFAULT_MODEL) -> Runnable:
    """Real Claude client, tool-bound. Callers may inject a fake model instead
    (e.g. in tests) by passing it directly to run_tool_calling_loop()."""
    return ChatAnthropic(model=model).bind_tools(tools)


def load_machine_context(
    customer_id: str,
    machine_serial: str,
    sink: list[dict[str, Any]],
) -> Iterator[OrchestratorChunk]:
    """Real scoping check via registry.invoke('get_machine_info', ...).

    Appends the registry result dict to `sink` (mirrors the tool_context.append
    pattern every MCP-calling agent already uses) so the caller can inspect
    `sink[0]['status']` after draining this generator.
    """
    yield OrchestratorChunk(type='step', content='Loading machine context…')
    result = registry.invoke(
        'get_machine_info',
        {'customer_id': customer_id, 'machine_serial': machine_serial},
    )
    yield OrchestratorChunk(type='tool', tool='get_machine_info', data=result)
    sink.append(result)


def run_tool_calling_loop(
    llm: BaseChatModel | Runnable,
    tools: list[AgentTool],
    *,
    system_prompt: str,
    user_message: str,
    history: list[BaseMessage] | None = None,
    new_messages_sink: list[BaseMessage] | None = None,
) -> Iterator[OrchestratorChunk]:
    """Stream Claude turns until it stops calling tools.

    `history` is prior conversation turns (Human/AI/Tool messages) for this
    thread, loaded by the caller from persisted state -- the system prompt is
    NOT part of it, since it's static per agent and re-added fresh every call
    rather than stored. If `new_messages_sink` is given, every message this
    turn adds (the new HumanMessage plus any ToolMessages/AIMessages) is
    appended to it once the turn finishes, so the caller can persist just the
    delta back into shared state instead of the whole reconstructed history.

    Each turn is streamed via llm.stream() and buffered locally rather than
    forwarded live. Once a turn completes:
      - no tool_calls -> it's the final answer. Replay the buffered deltas as
        `token` chunks (preserves live "typing" for the text the user actually
        reads in the single assistant bubble).
      - tool_calls present -> any narration text Claude produced before the
        call ("Let me check that…") is discarded, not streamed -- the chat UI
        renders exactly one assistant paragraph, so leaking that filler in
        would glue itself onto the final answer with no separator. Progress is
        communicated only via `step`/`tool` chunks, exactly like today.
    """
    tools_by_name = {t.tool.name: t for t in tools}
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        *(history or []),
        HumanMessage(content=user_message),
    ]
    turn_start = len(messages) - 1  # first message this turn added (the HumanMessage)

    while True:
        accumulated = None
        buffered_text: list[str] = []
        for chunk in llm.stream(messages):
            accumulated = chunk if accumulated is None else accumulated + chunk
            if chunk.text:
                buffered_text.append(chunk.text)

        messages.append(accumulated)

        if not accumulated.tool_calls:
            for piece in buffered_text:
                yield OrchestratorChunk(type='token', content=piece)
            if new_messages_sink is not None:
                new_messages_sink.extend(messages[turn_start:])
            return

        for call in accumulated.tool_calls:
            entry = tools_by_name[call['name']]
            yield OrchestratorChunk(type='step', content=entry.step_label)
            result = entry.tool.invoke(call['args'])
            yield OrchestratorChunk(type='tool', tool=call['name'], data=result)
            messages.append(
                ToolMessage(content=json.dumps(result, default=str), tool_call_id=call['id']),
            )
