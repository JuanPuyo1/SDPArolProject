"""LangGraph orchestrator — routes chat turns to the specialized agent nodes."""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import Annotated, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from apps.agents.agent_kit import DEFAULT_MODEL
from apps.agents.manuals_agent import ManualsAgent
from apps.agents.orders_business_agent import OrdersBusinessAgent
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.agents.telemetry_agent import TelemetryAgent
from apps.agents.troubleshooting_service_agent import TroubleshootingServiceAgent


class AgentIntent(str, Enum):
    ORDERS_BUSINESS = "orders_business"
    TROUBLESHOOTING_SERVICE = "troubleshooting_service"
    TELEMETRY = "telemetry"
    MANUALS = "manuals"


class _RouteDecision(BaseModel):
    """Structured output schema for the router LLM call."""

    agent: Literal[
        "orders_business", "troubleshooting_service", "manuals", "telemetry"
    ] = Field(
        description=(
            "'orders_business' for quotes, order status, invoices, "
            "contracts, warranty, or pricing/purchasing questions; "
            "'troubleshooting_service' for alarms, faults, breakdowns, "
            "diagnostics, or field-service ticket requests; "
            "'telemetry' for real-time or historical sensor readings, "
            "temperature, pressure, cycle count, operating speed, or vibration, and "
            "'manuals' for how-to/operating/adjustment/maintenance "
            "questions answered by the machine's documentation, with no "
            "active fault or alarm involved."
        ),
    )


_ROUTER_SYSTEM_PROMPT = """Classify the user's message for AROL's customer \
chat platform (industrial capping/filling machines) into exactly one of four \
agents:

- orders_business: quotes (including revision history), order status, \
invoices, contracts, warranty, pricing/purchasing.
- troubleshooting_service: alarms, faults, breakdowns, diagnostics, \
opening a field-service ticket.
- telemetry: machine sensor readings, historical telemetry points, cycle \
counts, temperature, pressure, vibration, or operating speed metrics.
- manuals: how to operate, adjust, or maintain the machine -- procedure and \
documentation questions that don't involve an active fault or alarm.

Pick whichever agent's domain the message best fits, based on its meaning \
rather than exact keyword matches. If the message is a greeting or is \
otherwise generic/ambiguous and doesn't clearly belong to orders_business, \
telemetry or manuals (e.g. "hi", "how can you help me?", "what can you do?"), default to \
troubleshooting_service -- it's the general-purpose front door for this \
platform."""


def build_router_llm():
    """Real Claude client bound to the routing decision schema. Callers may
    inject a fake model instead (e.g. in tests) via classify_intent(llm=...)."""
    return ChatAnthropic(model=DEFAULT_MODEL).with_structured_output(_RouteDecision)


def classify_intent(message: str, llm=None) -> AgentIntent:
    router = llm or build_router_llm()
    decision = router.invoke(
        [SystemMessage(content=_ROUTER_SYSTEM_PROMPT), HumanMessage(content=message)],
    )
    return AgentIntent(decision.agent)


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
    AgentIntent.ORDERS_BUSINESS: "Routing to the Orders/Business agent…",
    AgentIntent.TROUBLESHOOTING_SERVICE: "Routing to the Troubleshooting/Service agent…",
    AgentIntent.TELEMETRY: "Routing to the Telemetry agent…",
    AgentIntent.MANUALS: "Routing to the Manuals agent…",
}


def _router_node(state: ChatState) -> dict:
    intent = classify_intent(state["message"])
    writer = get_stream_writer()
    writer(
        OrchestratorChunk(
            type="step", content=_ROUTE_LABELS[intent], agent=intent.value
        )
    )
    return {"intent": intent.value}


def _orders_business_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in OrdersBusinessAgent().run(
        customer_id=state["customer_id"],
        machine_serial=state["machine_serial"],
        message=state["message"],
        attachments=state["attachments"],
        history=state["messages"],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {"messages": new_messages}


def _troubleshooting_service_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in TroubleshootingServiceAgent().run(
        customer_id=state["customer_id"],
        machine_serial=state["machine_serial"],
        message=state["message"],
        attachments=state["attachments"],
        history=state["messages"],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {"messages": new_messages}


def _telemetry_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in TelemetryAgent().run(
        customer_id=state["customer_id"],
        machine_serial=state["machine_serial"],
        message=state["message"],
        attachments=state["attachments"],
        history=state["messages"],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {"messages": new_messages}


def _manuals_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    new_messages: list[BaseMessage] = []
    for chunk in ManualsAgent().run(
        customer_id=state["customer_id"],
        machine_serial=state["machine_serial"],
        message=state["message"],
        attachments=state["attachments"],
        history=state["messages"],
        new_messages_sink=new_messages,
    ):
        writer(chunk)
    return {"messages": new_messages}


def _route(state: ChatState) -> str:
    return state["intent"]


def _build_graph():
    graph = StateGraph(ChatState)
    graph.add_node(AgentIntent.ORDERS_BUSINESS.value, _orders_business_node)
    graph.add_node(
        AgentIntent.TROUBLESHOOTING_SERVICE.value, _troubleshooting_service_node
    )
    graph.add_node(AgentIntent.TELEMETRY.value, _telemetry_node)
    graph.add_node(AgentIntent.MANUALS.value, _manuals_node)
    graph.add_node("router", _router_node)
    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _route,
        {
            AgentIntent.ORDERS_BUSINESS.value: AgentIntent.ORDERS_BUSINESS.value,
            AgentIntent.TROUBLESHOOTING_SERVICE.value: AgentIntent.TROUBLESHOOTING_SERVICE.value,
            AgentIntent.TELEMETRY.value: AgentIntent.TELEMETRY.value,
            AgentIntent.MANUALS.value: AgentIntent.MANUALS.value,
        },
    )
    graph.add_edge(AgentIntent.ORDERS_BUSINESS.value, END)
    graph.add_edge(AgentIntent.TROUBLESHOOTING_SERVICE.value, END)
    graph.add_edge(AgentIntent.TELEMETRY.value, END)
    graph.add_edge(AgentIntent.MANUALS.value, END)
    # MemorySaver keeps each thread's ChatState (including `messages`) in this
    # process's memory, keyed by the thread_id passed in run()'s config below.
    # It's per-process and resets on restart -- fine for a single-worker
    # deployment; swap for a persistent checkpointer (e.g. SqliteSaver) if the
    # backend ever runs multiple workers or needs history to survive restarts.
    return graph.compile(checkpointer=MemorySaver())


_compiled_graph = _build_graph()


class LangGraphOrchestrator:
    """Routes each chat turn to the orders/business, troubleshooting/service,
    telemetry, or manuals agent via a compiled LangGraph StateGraph, streaming
    each agent's OrchestratorChunks straight through via LangGraph's custom
    stream mode.

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
            "customer_id": customer_id,
            "machine_serial": machine_serial,
            "message": message,
            "attachments": attachments or [],
            "intent": "",
            "messages": [],
        }
        config = {"configurable": {"thread_id": f"{customer_id}:{session_id}"}}
        for chunk in _compiled_graph.stream(state, config, stream_mode="custom"):
            yield chunk
        yield OrchestratorChunk(type="done")
