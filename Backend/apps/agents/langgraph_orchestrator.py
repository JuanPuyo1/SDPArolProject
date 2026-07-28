"""LangGraph orchestrator — routes chat turns to the specialized agent nodes."""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import Enum
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

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
    for chunk in OrdersBusinessAgent().run(
        customer_id=state['customer_id'],
        machine_serial=state['machine_serial'],
        message=state['message'],
        attachments=state['attachments'],
    ):
        writer(chunk)
    return {}


def _troubleshooting_service_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    for chunk in TroubleshootingServiceAgent().run(
        customer_id=state['customer_id'],
        machine_serial=state['machine_serial'],
        message=state['message'],
        attachments=state['attachments'],
    ):
        writer(chunk)
    return {}


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
    return graph.compile()


_compiled_graph = _build_graph()


class LangGraphOrchestrator:
    """Routes each chat turn to the orders/business or troubleshooting/service
    agent via a compiled LangGraph StateGraph, streaming each agent's
    OrchestratorChunks straight through via LangGraph's custom stream mode."""

    def run(
        self,
        *,
        customer_id: str,
        machine_serial: str,
        message: str,
        attachments: list[ChatAttachmentRef] | None = None,
    ) -> Iterator[OrchestratorChunk]:
        state: ChatState = {
            'customer_id': customer_id,
            'machine_serial': machine_serial,
            'message': message,
            'attachments': attachments or [],
            'intent': '',
        }
        for chunk in _compiled_graph.stream(state, stream_mode='custom'):
            yield chunk
        yield OrchestratorChunk(type='done')
