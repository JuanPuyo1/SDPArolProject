"""Fleet orchestrator — single-node LangGraph graph for the general,
company-scoped chatbot.

Deliberately separate from langgraph_orchestrator.py's router/fan-out graph:
this chatbot always answers with exactly one agent (FleetAgent), is not
scoped to a machine_serial, and must keep working for a company that owns
zero machines -- see the plan doc's "Why a separate graph" section. It still
reuses the same OrchestratorChunk streaming protocol and a LangGraph
MemorySaver checkpointer (its own instance, so fleet conversations never mix
with per-machine ones) so the frontend can reuse its existing SSE handling.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from apps.agents.fleet_agent import FleetAgent
from apps.agents.ports import OrchestratorChunk


class FleetChatState(TypedDict):
    customer_id: str
    message: str
    # Conversation history for this thread (session_id), carried across turns
    # by the checkpointer -- same "only clean Human/AI text, no tool
    # transcripts" convention as ChatState.messages in the per-machine graph.
    messages: Annotated[list[BaseMessage], add_messages]


def _fleet_node(state: FleetChatState) -> dict:
    writer = get_stream_writer()
    answer: list[str] = []

    for chunk in FleetAgent().run(
        customer_id=state['customer_id'],
        message=state['message'],
        history=state.get('messages'),
        emit_tokens=True,
        answer_sink=answer,
    ):
        writer(chunk)

    text = answer[0] if answer else ''
    return {
        'messages': [
            HumanMessage(content=state['message']),
            AIMessage(content=text),
        ]
    }


def _build_fleet_graph():
    graph = StateGraph(FleetChatState)
    graph.add_node('fleet', _fleet_node)
    graph.set_entry_point('fleet')
    graph.add_edge('fleet', END)
    return graph.compile(checkpointer=MemorySaver())


_compiled_fleet_graph = _build_fleet_graph()


class FleetOrchestrator:
    """Streams one FleetAgent reply per turn, resuming conversation history
    from the checkpointer keyed by customer_id:session_id (mirrors
    LangGraphOrchestrator's thread_id scheme, under its own 'fleet:' prefix
    so the two graphs' checkpoints never collide)."""

    def run(
        self,
        *,
        customer_id: str,
        message: str,
        session_id: str,
    ) -> Iterator[OrchestratorChunk]:
        state: FleetChatState = {
            'customer_id': customer_id,
            'message': message,
            'messages': [],
        }
        config = {'configurable': {'thread_id': f'fleet:{customer_id}:{session_id}'}}
        for chunk in _compiled_fleet_graph.stream(state, config, stream_mode='custom'):
            yield chunk
        yield OrchestratorChunk(type='done')


class StubFleetOrchestrator:
    """OrchestratorPort-shaped adapter for ORCHESTRATOR_BACKEND=stub: runs
    FleetAgent directly with no checkpointer (mirrors StubOrchestrator's
    one-shot delegation to TroubleshootingServiceAgent) -- session_id is
    accepted for interface parity but each call starts fresh."""

    def run(
        self,
        *,
        customer_id: str,
        message: str,
        session_id: str,
    ) -> Iterator[OrchestratorChunk]:
        yield from FleetAgent().run(customer_id=customer_id, message=message)
        yield OrchestratorChunk(type='done')
