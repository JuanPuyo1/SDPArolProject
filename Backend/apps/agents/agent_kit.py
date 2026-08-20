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
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import create_model

from apps.agents.llm_factory import get_active_model_name, get_tool_calling_llm
from apps.agents.ports import OrchestratorChunk
from apps.mcp_server import registry

# Fields injected by mcp_tool() from the authenticated request rather than
# exposed as LLM-fillable tool args -- the model must never be trusted to
# supply tenant scope (see mcp_tool()'s docstring).
_SCOPE_FIELDS = ('customer_id', 'machine_serial')

DEFAULT_MODEL = get_active_model_name()
DEFAULT_MAX_ITERATIONS = 8

# Appended to every agent's system prompt (see run_tool_calling_loop) so the
# Access Model's "declined explicitly, never as an empty result" rule (see
# README_AROL.md) is enforced once, centrally -- not left to each agent's
# prompt to remember, and not left to emergent LLM phrasing. A tool result
# with code=FORBIDDEN means the request is outside the caller's permitted
# visibility domain, not that no data exists; wording it as "not found" would
# be indistinguishable from the empty-result case the spec explicitly
# prohibits.
_ACCESS_DENIAL_INSTRUCTION = """

If a tool result has status "error" and code "FORBIDDEN", that means this \
information is outside your role's permitted access level for this account \
-- it does NOT mean the data doesn't exist. Tell the user plainly and \
explicitly that their account's role does not have permission to view this \
category of information (name the category, e.g. commercial/quote data or \
operational/telemetry data), and stop there for that part of the request. \
Never reword a FORBIDDEN denial as "not found", "no data available", "I \
couldn't find", or any other phrasing that reads as if nothing exists. \
Never try a different tool to route around the denial."""


class AgentTool(NamedTuple):
    """A LangChain tool paired with the `step` chunk label shown while it runs."""

    tool: BaseTool
    step_label: str


def build_llm(tools: list[BaseTool], *, model: str | None = None) -> Runnable:
    """Tool-bound LLM client (Claude or Local Model depending on LLM_PROVIDER).
    Callers may inject a fake model instead (e.g. in tests) by passing it directly
    to run_tool_calling_loop()."""
    return get_tool_calling_llm(tools, model=model)


def mcp_tool(
    name: str,
    *,
    customer_id: str,
    machine_serial: str,
    step_label: str | None = None,
) -> AgentTool:
    """Build a LangChain tool from an MCP ToolSpec (apps.mcp_server.registry).

    name, description, and argument schema all come from the ToolSpec --
    the single source of truth for what a tool does -- instead of being
    hand-copied into a `@tool`-decorated docstring per agent. A stale
    docstring that drifts from ToolSpec.description is a real cost (the LLM
    picks tools based on what it's told they do), and there's now nowhere
    for that drift to happen: change the description once, in registry.py,
    and every agent that calls this picks it up automatically.

    customer_id/machine_serial are injected here from the authenticated
    request and stripped out of the schema the LLM sees -- the model must
    never be trusted to supply tenant scope, only genuine tool arguments.
    """
    spec = registry.get_tool(name)
    if spec is None:
        raise ValueError(f'Unknown MCP tool: {name!r}')

    scoped_fields = set(_SCOPE_FIELDS) & set(spec.input_model.model_fields)
    public_fields = {
        field_name: (field.annotation, field)
        for field_name, field in spec.input_model.model_fields.items()
        if field_name not in scoped_fields
    }
    args_schema = create_model(f'{spec.name}_Args', **public_fields)
    scope = {'customer_id': customer_id, 'machine_serial': machine_serial}

    def _call(**kwargs: Any) -> dict:
        params = {**kwargs, **{field: scope[field] for field in scoped_fields}}
        return registry.invoke(spec.name, params)

    tool = StructuredTool.from_function(
        func=_call,
        name=spec.name,
        description=spec.description,
        args_schema=args_schema,
    )
    return AgentTool(tool, step_label or f'Calling {spec.name}…')


def build_agent_tools(
    agent_tags: str | set[str],
    *,
    customer_id: str,
    machine_serial: str,
    step_labels: dict[str, str] | None = None,
) -> list[AgentTool]:
    """Every MCP tool tagged for this agent in the registry, built via
    mcp_tool(). Add a tool to an agent by tagging it in registry.py -- no
    agent file needs editing to pick it up.

    `agent_tags` is usually a single AgentName, but may be a set for an
    agent that currently spans multiple registry domains (e.g.
    TroubleshootingServiceAgent covers 'troubleshooting'/'telemetry'/
    'service' until those split into their own agents).

    registry.list_tools(agent=X) also returns 'shared' tools (get_machine_info,
    echo, ...) as a convenience for discovery UIs -- those are excluded here
    on purpose: they're either fetched explicitly by load_machine_context()
    already, or debug-only, not meant to be LLM-callable by every agent.
    """
    tags = {agent_tags} if isinstance(agent_tags, str) else agent_tags
    step_labels = step_labels or {}
    seen: set[str] = set()
    tools: list[AgentTool] = []
    for tag in tags:
        for meta in registry.list_tools(agent=tag):
            if meta['agent'] != tag or meta['name'] in seen:
                continue
            seen.add(meta['name'])
            tools.append(
                mcp_tool(
                    meta['name'],
                    customer_id=customer_id,
                    machine_serial=machine_serial,
                    step_label=step_labels.get(meta['name']),
                ),
            )
    return tools


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
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> Iterator[OrchestratorChunk]:
    """Stream Claude turns until it stops calling tools.

    `history` is prior conversation turns (Human/AI/Tool messages) for this
    thread, loaded by the caller from persisted state -- the system prompt is
    NOT part of it, since it's static per agent and re-added fresh every call
    rather than stored. If `new_messages_sink` is given, every message this
    turn adds (the new HumanMessage plus any ToolMessages/AIMessages) is
    appended to it once the turn finishes, so the caller can persist just the
    delta back into shared state instead of the whole reconstructed history.

    `max_iterations` caps the number of tool-calling round-trips this turn
    may take: without it a model that never stops calling tools loops (and
    bills) forever. On exhaustion, whatever was gathered so far is still
    persisted to `new_messages_sink` and an `error` chunk is yielded instead
    of a final answer. A hallucinated tool name or a tool that raises is fed
    back to the model as an error ToolMessage rather than crashing the
    generator, mirroring how every real tool result already carries a
    {'status': 'error', ...} envelope (see registry.invoke).

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
        SystemMessage(content=system_prompt + _ACCESS_DENIAL_INSTRUCTION),
        *(history or []),
        HumanMessage(content=user_message),
    ]
    turn_start = len(messages) - 1  # first message this turn added (the HumanMessage)

    for _ in range(max_iterations):
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
            entry = tools_by_name.get(call['name'])
            if entry is None:
                result = {'status': 'error', 'message': f"Unknown tool: {call['name']}"}
            else:
                yield OrchestratorChunk(type='step', content=entry.step_label)
                try:
                    args = call.get('args', {})
                    if isinstance(args, str):
                        args = json.loads(args) if args.strip() else {}
                    result = entry.tool.invoke(args)
                except Exception as exc:  # noqa: BLE001
                    # Reported back to the model as a tool error, not raised.
                    result = {'status': 'error', 'message': f'{call["name"]} failed: {exc}'}
            yield OrchestratorChunk(type='tool', tool=call['name'], data=result)
            tool_call_id = call.get('id') or f"call_{len(messages)}"
            messages.append(
                ToolMessage(content=json.dumps(result, default=str), tool_call_id=tool_call_id),
            )

    if new_messages_sink is not None:
        new_messages_sink.extend(messages[turn_start:])
    yield OrchestratorChunk(
        type='error',
        message=f'Gave up after {max_iterations} tool-calling round-trips without a final answer.',
    )
