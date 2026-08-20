"""LangGraph orchestrator — plans a turn into per-agent subtasks, fans them
out to the specialist agents in parallel, and synthesizes one reply.

Topology:

    router ──(Send xN)──> [orders_business | troubleshooting_service |
                           telemetry | manuals] ──> synthesizer ──> END

The router emits a *list* of tasks rather than a single label, so a message
that spans two domains ("what does this alarm mean and what does the manual
say to do about it?") reaches both agents in one turn instead of being
refused by whichever one happened to win the classification.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import Annotated, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send
from pydantic import BaseModel, Field

from apps.agents.agent_kit import DEFAULT_MODEL
from apps.agents.manuals_agent import ManualsAgent
from apps.agents.orders_business_agent import OrdersBusinessAgent
from apps.agents.ports import ChatAttachmentRef, OrchestratorChunk
from apps.agents.telemetry_agent import TelemetryAgent
from apps.agents.troubleshooting_service_agent import TroubleshootingServiceAgent


class AgentIntent(str, Enum):
    ORDERS_BUSINESS = 'orders_business'
    TROUBLESHOOTING_SERVICE = 'troubleshooting_service'
    TELEMETRY = 'telemetry'
    MANUALS = 'manuals'


_AGENT_RUNNERS = {
    AgentIntent.ORDERS_BUSINESS: OrdersBusinessAgent,
    AgentIntent.TROUBLESHOOTING_SERVICE: TroubleshootingServiceAgent,
    AgentIntent.TELEMETRY: TelemetryAgent,
    AgentIntent.MANUALS: ManualsAgent,
}

_ROUTE_LABELS = {
    AgentIntent.ORDERS_BUSINESS: 'Routing to the Orders/Business agent…',
    AgentIntent.TROUBLESHOOTING_SERVICE: 'Routing to the Troubleshooting/Service agent…',
    AgentIntent.TELEMETRY: 'Routing to the Telemetry agent…',
    AgentIntent.MANUALS: 'Routing to the Manuals agent…',
}


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------

class _AgentTask(BaseModel):
    agent: Literal[
        'orders_business', 'troubleshooting_service', 'manuals', 'telemetry',
    ]
    subtask: str = Field(
        description=(
            'The self-contained question this agent must answer. Resolve every '
            'referent from earlier turns inline -- the agent receiving this '
            'never sees the raw user message, so "that alarm" or "the second '
            'ticket" must be replaced with the actual code or ID.'
        ),
    )


class _RouteDecision(BaseModel):
    tasks: list[_AgentTask] = Field(
        description=(
            'One entry per agent needed to answer the message. Most messages '
            'need exactly one; a message spanning two domains needs two.'
        ),
        min_length=1,
        max_length=3,
    )


_ROUTER_SYSTEM_PROMPT = """You plan how to answer a user message on AROL's \
customer chat platform (industrial capping/filling machines) by splitting it \
across specialist agents.

Available agents:
- orders_business: quotes (including revision history), order status, \
invoices, contracts, warranty, pricing/purchasing.
- troubleshooting_service: alarms, alarm history, faults, breakdowns, \
diagnostics, error codes, and looking up or opening field-service tickets.
- telemetry: sensor readings and historical telemetry points -- cycle counts, \
temperature, pressure, vibration, operating speed.
- manuals: how to operate, adjust, maintain, or repair the machine according \
to its documentation -- procedures, settings, and part references.

Return one task per agent the message actually needs.

- Most messages need exactly ONE task. Do not split a single-domain question.
- Split into TWO OR THREE tasks when the message genuinely spans domains. \
"What does alarm AL057 mean and what does the manual say to fix it?" needs \
troubleshooting_service (what the alarm is) AND manuals (the corrective \
procedure). "Is this fault covered by warranty?" needs \
troubleshooting_service AND orders_business.
- Each `subtask` must stand alone. The receiving agent sees ONLY the subtask \
text, never the user's original wording and never the conversation. Use the \
prior conversation below to replace every pronoun and back-reference with the \
concrete alarm code, ticket ID, quote number, or metric name. If the user \
says "the linked alarms" and the previous turn listed AL057_BOTTLE_TOO_HIGH, \
write AL057_BOTTLE_TOO_HIGH into the subtask.
- For a greeting or a vague message ("hi", "what can you do?"), return a \
single troubleshooting_service task -- it is the general-purpose front door.
"""


def build_router_llm():
    """Real Claude client bound to the routing decision schema. Callers may
    inject a fake model instead (e.g. in tests) via plan_tasks(llm=...)."""
    return ChatAnthropic(model=DEFAULT_MODEL).with_structured_output(_RouteDecision)


def _as_text(content) -> str:
    """Flatten LangChain message content (str, or list of content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(
            block.get('text', '')
            for block in content
            if isinstance(block, dict) and block.get('type') == 'text'
        )
    return str(content)


def _format_history(history: list[BaseMessage] | None, *, max_turns: int = 10) -> str:
    """Render the tail of the conversation for the router prompt.

    The router needs enough context to resolve "the linked alarms" against
    whatever the previous turn actually returned. Only Human/AI text is
    included: tool transcripts are far too large and the assistant's final
    answer already restates the codes and IDs the user is referring to.
    """
    if not history:
        return ''
    lines: list[str] = []
    for msg in history[-max_turns:]:
        text = _as_text(msg.content).strip()
        if not text:
            continue
        role = 'User' if isinstance(msg, HumanMessage) else 'Assistant'
        lines.append(f'{role}: {text}')
    if not lines:
        return ''
    return '\n\nPrior conversation (most recent last):\n' + '\n'.join(lines)


def plan_tasks(
    message: str,
    history: list[BaseMessage] | None = None,
    llm=None,
) -> list[dict]:
    """Return [{'agent': ..., 'subtask': ...}, ...] for this turn.

    Falls back to a single troubleshooting_service task carrying the raw
    message if the router returns nothing usable -- a routing failure should
    degrade to "the front door answers it", never to an empty fan-out that
    would leave the synthesizer with nothing to say.
    """
    router = llm or build_router_llm()
    decision = router.invoke([
        SystemMessage(content=_ROUTER_SYSTEM_PROMPT + _format_history(history)),
        HumanMessage(content=message),
    ])

    tasks: list[dict] = []
    seen: set[str] = set()
    for task in getattr(decision, 'tasks', None) or []:
        if task.agent in seen:
            # Two subtasks for one agent would dispatch the same node twice in
            # one superstep. Fold them into a single richer subtask instead.
            for existing in tasks:
                if existing['agent'] == task.agent:
                    existing['subtask'] += f' Also: {task.subtask}'
            continue
        seen.add(task.agent)
        tasks.append({'agent': task.agent, 'subtask': task.subtask})

    if not tasks:
        tasks = [{
            'agent': AgentIntent.TROUBLESHOOTING_SERVICE.value,
            'subtask': message,
        }]
    return tasks


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

def _accumulate_outputs(
    left: list[dict] | None,
    right: list[dict] | None,
) -> list[dict]:
    """Reducer for `agent_outputs`: concurrency-safe append, explicit reset.

    Parallel agent nodes each return a one-element list, which must merge
    rather than collide (a plain `str`/`list` field raises InvalidUpdateError
    when two nodes write it in the same superstep).

    A plain `operator.add` would be wrong here, though: `agent_outputs` is
    checkpointed, so turn 2 would still carry turn 1's answers and the
    synthesizer would merge stale content. An empty list is therefore treated
    as an explicit "clear", which `_router_node` sends at the start of every
    turn.
    """
    if right is not None and len(right) == 0:
        return []
    return (left or []) + (right or [])


class ChatState(TypedDict):
    customer_id: str
    machine_serial: str
    message: str
    attachments: list[ChatAttachmentRef]
    # Set per-agent by the Send payload in _dispatch, not by any node return:
    # each fanned-out branch gets its own value, so it never collides.
    subtask: str
    # Planned this turn by the router; last-write-wins is correct since only
    # the router writes it.
    tasks: list[dict]
    # First planned agent, kept for frontend attribution and stub parity.
    intent: str
    agent_outputs: Annotated[list[dict], _accumulate_outputs]
    # Conversation history for this thread (session_id), carried across turns
    # by the checkpointer.
    #
    # IMPORTANT: only the synthesizer writes here, and only a clean
    # HumanMessage/AIMessage pair. Specialist agents deliberately do NOT
    # persist their tool transcripts: under fan-out, two agents' tool_use
    # blocks would interleave into one history, and replaying that history to
    # an agent bound to a different tool set sends it tool_use blocks for
    # tools it does not have. Keeping history to plain text also bounds
    # context growth -- retrieved manual passages are large and would
    # otherwise accumulate for the life of the session.
    messages: Annotated[list[BaseMessage], add_messages]


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------

def _router_node(state: ChatState) -> dict:
    tasks = plan_tasks(state['message'], state.get('messages'))
    writer = get_stream_writer()
    for task in tasks:
        intent = AgentIntent(task['agent'])
        writer(OrchestratorChunk(
            type='step',
            content=_ROUTE_LABELS[intent],
            agent=intent.value,
        ))
    return {
        'tasks': tasks,
        'intent': tasks[0]['agent'],
        'agent_outputs': [],  # reset last turn's answers (see _accumulate_outputs)
    }


def _make_agent_node(intent: AgentIntent):
    """Build the LangGraph node for one specialist agent.

    The four nodes differed only by which class they instantiated, so they're
    generated rather than copy-pasted -- adding the fifth agent is one entry
    in _AGENT_RUNNERS.
    """
    runner_cls = _AGENT_RUNNERS[intent]

    def node(state: ChatState) -> dict:
        writer = get_stream_writer()
        answer: list[str] = []
        subtask = state.get('subtask') or state['message']

        for chunk in runner_cls().run(
            customer_id=state['customer_id'],
            machine_serial=state['machine_serial'],
            message=subtask,
            attachments=state.get('attachments') or [],
            history=state.get('messages'),
            # Only the synthesizer streams tokens. Two agents running in
            # parallel would otherwise interleave two half-answers into the
            # single assistant bubble the chat UI renders.
            emit_tokens=False,
            answer_sink=answer,
        ):
            # step/tool chunks still stream live so the user sees both agents
            # working ("Checking alarm history…" / "Searching manual…").
            writer(chunk)

        return {'agent_outputs': [{
            'agent': intent.value,
            'subtask': subtask,
            'answer': answer[0] if answer else '',
        }]}

    node.__name__ = f'{intent.value}_node'
    return node


_SYNTHESIZER_SYSTEM_PROMPT = """You are the response synthesizer for AROL's \
customer chat platform. Below are answers from specialist agents that worked \
in parallel on different parts of one user question.

Merge them into a single coherent reply addressed to the user.

- Preserve every alarm code, error code, ticket ID, quote/order number, page \
number, and section reference exactly as written. Never renumber, abbreviate, \
or paraphrase an identifier.
- Do not mention agents, routing, or that the work was split up. The user \
asked one question and gets one answer.
- If an agent reported that its part is outside its tools, omit that filler \
rather than repeating it -- unless it means part of the question went \
genuinely unanswered, in which case say plainly what could not be answered.
- If an agent reported that the account's role lacks permission to view a \
category of information, reproduce that denial explicitly and keep it \
distinct from "no data found". Never soften it, merge it away, or imply the \
data does not exist.
- Keep the answer concise and do not add facts that are not in the agent \
answers below."""


def _synthesizer_node(state: ChatState) -> dict:
    writer = get_stream_writer()
    outputs = state.get('agent_outputs') or []

    if not outputs:
        text = "I wasn't able to produce an answer for that. Could you rephrase?"
        writer(OrchestratorChunk(type='token', content=text))
    elif len(outputs) == 1:
        # Single-agent turn (the common case): the agent's answer IS the
        # reply. Skip the synthesis LLM call entirely -- paying for a merge
        # of one item would add latency and cost to ~80% of turns for nothing.
        text = outputs[0]['answer']
        writer(OrchestratorChunk(type='token', content=text))
    else:
        writer(OrchestratorChunk(type='step', content='Combining agent findings…'))
        sections = '\n\n'.join(
            f"[{out['agent']}] asked: {out['subtask']}\nanswered: {out['answer']}"
            for out in outputs
        )
        llm = ChatAnthropic(model=DEFAULT_MODEL)
        pieces: list[str] = []
        for chunk in llm.stream([
            SystemMessage(content=_SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"The user asked: {state['message']}\n\n"
                f'Specialist answers:\n\n{sections}'
            )),
        ]):
            if chunk.text:
                pieces.append(chunk.text)
                writer(OrchestratorChunk(type='token', content=chunk.text))
        text = ''.join(pieces)

    # The only write to `messages` in the whole graph: one clean turn,
    # replayable by any agent regardless of its tool bindings.
    return {'messages': [
        HumanMessage(content=state['message']),
        AIMessage(content=text),
    ]}


def _dispatch(state: ChatState) -> list[Send]:
    """Fan out one Send per planned task.

    Each Send payload becomes that branch's input state, which is how the
    per-agent `subtask` reaches the node without ever being written to shared
    state (where parallel branches would collide on the same key).
    """
    return [
        Send(task['agent'], {
            'customer_id': state['customer_id'],
            'machine_serial': state['machine_serial'],
            'message': state['message'],
            'attachments': state.get('attachments') or [],
            'messages': state.get('messages') or [],
            'subtask': task['subtask'],
        })
        for task in state['tasks']
    ]


def _build_graph():
    graph = StateGraph(ChatState)

    graph.add_node('router', _router_node)
    for intent in AgentIntent:
        graph.add_node(intent.value, _make_agent_node(intent))
    graph.add_node('synthesizer', _synthesizer_node)

    graph.set_entry_point('router')
    graph.add_conditional_edges(
        'router',
        _dispatch,
        [intent.value for intent in AgentIntent],
    )
    for intent in AgentIntent:
        graph.add_edge(intent.value, 'synthesizer')
    graph.add_edge('synthesizer', END)

    # MemorySaver keeps each thread's ChatState (including `messages`) in this
    # process's memory, keyed by the thread_id passed in run()'s config below.
    # It's per-process and resets on restart -- fine for a single-worker
    # deployment; swap for a persistent checkpointer (SqliteSaver or, better
    # given Postgres is already in the stack, PostgresSaver) if the backend
    # ever runs multiple workers or needs history to survive restarts.
    return graph.compile(checkpointer=MemorySaver())


_compiled_graph = _build_graph()


class LangGraphOrchestrator:
    """Plans each chat turn into per-agent subtasks, runs those agents in
    parallel, and streams one synthesized reply.

    Conversation history is real LangGraph state: calling run() again with the
    same session_id resumes `messages` from where the previous turn left off.
    The checkpoint thread_id is `customer_id:session_id`, not the bare
    session_id, so a guessed/reused UUID can never splice a request into
    another customer's history -- session_id only ever picks a thread *within*
    that customer's own namespace, mirroring the tenant scoping already
    enforced on tools.
    """

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
            'subtask': '',
            'tasks': [],
            'intent': '',
            'agent_outputs': [],
            'messages': [],
        }
        config = {'configurable': {'thread_id': f'{customer_id}:{session_id}'}}
        for chunk in _compiled_graph.stream(state, config, stream_mode='custom'):
            yield chunk
        yield OrchestratorChunk(type='done')