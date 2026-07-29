"""LangGraph orchestrator — routes chat turns to the specialized agent nodes."""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import Enum
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from apps.agents.orders_business_agent import OrdersBusinessAgent
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.agents.troubleshooting_service_agent import TroubleshootingServiceAgent


class AgentIntent(str, Enum):
    ORDERS_BUSINESS = 'orders_business'
    TROUBLESHOOTING_SERVICE = 'troubleshooting_service'


_ORDERS_BUSINESS_PATTERN = re.compile(
    r'\b(quote|quotation|order|invoice|contract|warranty|price|pricing|purchase)\b',
    re.IGNORECASE,
)


def classify_intent(message: str) -> AgentIntent:
    if _ORDERS_BUSINESS_PATTERN.search(message):
        return AgentIntent.ORDERS_BUSINESS
    return AgentIntent.TROUBLESHOOTING_SERVICE


class ChatState(TypedDict):
    customer_id: str
    machine_serial: str
    message: str
    attachments: list[ChatAttachmentRef]
    intent: str
    # Conversation history for this thread (session_id), carried across turns
    # by the checkpointer. add_messages appends by message id rather than
    # overwriting, so nodes only ever need to return the *new* messages a
    # turn produced -- never the full accumulated list.
    messages: Annotated[list[BaseMessage], add_messages]


_ROUTE_LABELS = {
    AgentIntent.ORDERS_BUSINESS: 'Routing to the Orders/Business agent…',
    AgentIntent.TROUBLESHOOTING_SERVICE: 'Routing to the Troubleshooting/Service agent…',
}


def _router_node(state: ChatState) -> dict:
    intent = classify_intent(state['message'])
    writer = get_stream_writer()
    writer(OrchestratorChunk(type='step', content=_ROUTE_LABELS[intent]))
    return {'intent': intent.value}


def _orders_business_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in OrdersBusinessAgent().run(
        customer_id=state['customer_id'],
        machine_serial=state['machine_serial'],
        message=state['message'],
        attachments=state['attachments'],
        history=state['messages'],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {'messages': new_messages}


def _troubleshooting_service_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in TroubleshootingServiceAgent().run(
        customer_id=state['customer_id'],
        machine_serial=state['machine_serial'],
        message=state['message'],
        attachments=state['attachments'],
        history=state['messages'],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {'messages': new_messages}


def _route(state: ChatState) -> str:
    return state['intent']


def _build_graph():
    graph = StateGraph(ChatState)
    graph.add_node(AgentIntent.ORDERS_BUSINESS.value, _orders_business_node)
    graph.add_node(AgentIntent.TROUBLESHOOTING_SERVICE.value, _troubleshooting_service_node)
    graph.add_node('router', _router_node)
    graph.set_entry_point('router')
    graph.add_conditional_edges(
        'router',
        _route,
        {
            AgentIntent.ORDERS_BUSINESS.value: AgentIntent.ORDERS_BUSINESS.value,
            AgentIntent.TROUBLESHOOTING_SERVICE.value: AgentIntent.TROUBLESHOOTING_SERVICE.value,
        },
    )
    graph.add_edge(AgentIntent.ORDERS_BUSINESS.value, END)
    graph.add_edge(AgentIntent.TROUBLESHOOTING_SERVICE.value, END)
    # MemorySaver keeps each thread's ChatState (including `messages`) in this
    # process's memory, keyed by the thread_id passed in run()'s config below.
    # It's per-process and resets on restart -- fine for a single-worker
    # deployment; swap for a persistent checkpointer (e.g. SqliteSaver) if the
    # backend ever runs multiple workers or needs history to survive restarts.
    return graph.compile(checkpointer=MemorySaver())


_compiled_graph = _build_graph()


class LangGraphOrchestrator:
    """Routes each chat turn to the orders/business or troubleshooting/service
    agent via a compiled LangGraph StateGraph, streaming each agent's
    OrchestratorChunks straight through via LangGraph's custom stream mode.

    Conversation history is real LangGraph state now, not a value discarded
    at the end of each run(): calling run() again with the same session_id
    resumes `messages` from where the previous turn left off. The checkpoint
    thread_id is `customer_id:session_id`, not the bare session_id, so a
    guessed/reused UUID can never splice a request into another customer's
    history -- session_id only ever picks a thread *within* that customer's
    own namespace, mirroring the tenant scoping already enforced on tools."""

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        session_id: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        state: ChatState = {
            'customer_id': customer_id,
            'machine_serial': machine_serial,
            'message': message,
            'attachments': attachments or [],
            'intent': '',
            'messages': [],
        }
        config = {'configurable': {'thread_id': f'{customer_id}:{session_id}'}}
        for chunk in _compiled_graph.stream(state, config, stream_mode='custom'):
            yield chunk
        yield OrchestratorChunk(type='done')
