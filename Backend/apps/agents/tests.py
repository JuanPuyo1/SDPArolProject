"""Tests for chat SSE endpoint, stub/langgraph orchestrators, and routing.

These tests never hit the real Claude API. Instead they inject a small
scripted fake in place of the LLM (see _ScriptedLLM below) so the tests stay
fast/deterministic and verify our own plumbing -- tool-calling loop,
tenant scoping, chunk sequencing -- rather than Claude's actual reasoning.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from langchain_core.messages import AIMessageChunk

from apps.agents.langgraph_orchestrator import AgentIntent, LangGraphOrchestrator, classify_intent
from apps.agents.stub_orchestrator import StubOrchestrator
from apps.machines.models import Machine


def _tool_call_turn(name: str, args: dict, call_id: str = 'call_1') -> list[AIMessageChunk]:
    """One streamed turn: a single delta carrying a complete tool call."""
    return [
        AIMessageChunk(
            content='',
            tool_calls=[{'name': name, 'args': args, 'id': call_id, 'type': 'tool_call'}],
        ),
    ]


def _text_turn(text: str) -> list[AIMessageChunk]:
    """One streamed turn: split into two deltas to exercise the buffer-then-
    replay path in run_tool_calling_loop (only the confirmed-final turn's
    text should ever reach a `token` chunk)."""
    mid = len(text) // 2
    return [AIMessageChunk(content=text[:mid]), AIMessageChunk(content=text[mid:])]


class _ScriptedLLM:
    """Minimal stand-in for a LangChain chat model. run_tool_calling_loop()
    only ever calls .stream(messages), so that's the only method needed."""

    def __init__(self, turns: list[list[AIMessageChunk]]) -> None:
        self._turns = iter(turns)

    def stream(self, _messages):
        yield from next(self._turns)


def _make_machine(owner) -> Machine:
    return Machine.objects.create(
        owner=owner,
        serial_number='A3279',
        model='CLOSYS EAGLE VP',
        full_model='M - CLOSYS EAGLE VP',
        manufacturing_year=2014,
        description='Test machine',
        machine_type='Capping machine',
        pitch_diameter='550 mm',
        heads=1,
        rotation='Clockwise',
        weight_value='350',
        productive_capacity_value='1800',
        electrical_main_supply='575 V',
        electrical_auxiliary_supply='24 V',
        electrical_total_installed_power='2.24 kW',
        pneumatic_sterile_air_capacity='n/a',
        pneumatic_min_pressure='6 bar',
        pneumatic_max_pressure='8 bar',
        operating_temperature='5-40 C',
        operating_environment='Indoor',
        operating_noise='<80 dB',
    )


class StubOrchestratorTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        _make_machine(self.user)

    def test_stub_calls_mcp_tools_and_streams_final_answer(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn('search_error_codes', {'query': 'E042 star-wheel jam'}),
                _text_turn('Error E042 indicates a star-wheel jam. Clear the jam and reset the alarm.'),
            ],
        )
        with patch('apps.agents.troubleshooting_service_agent.build_llm', return_value=llm):
            orchestrator = StubOrchestrator()
            chunks = list(
                orchestrator.run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='Alarm E042 star-wheel jam',
                    session_id='session-1',
                ),
            )

        types = [c.type for c in chunks]
        self.assertIn('step', types)
        self.assertIn('tool', types)
        self.assertIn('token', types)
        self.assertEqual(types[-1], 'done')

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('get_machine_info', tool_names)
        self.assertIn('search_error_codes', tool_names)

        # get_machine_info's result is real (not scripted) -- confirms the
        # actual scoping/registry call ran, not just the fake narration.
        machine_chunk = next(c for c in chunks if c.tool == 'get_machine_info')
        self.assertIsNotNone(machine_chunk.data)
        assert machine_chunk.data is not None
        self.assertEqual(machine_chunk.data['data']['machine']['serialNumber'], 'A3279')

        text = ''.join(c.content for c in chunks if c.type == 'token')
        self.assertIn('star-wheel jam', text)

    def test_service_intent_opens_ticket(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn(
                    'create_ticket',
                    {
                        'subject': 'Machine keeps stopping',
                        'description': 'Please send a technician — machine keeps stopping',
                        'priority': 'high',
                        'category': 'support',
                    },
                ),
                _text_turn('A field-support ticket has been opened for you.'),
            ],
        )
        with patch('apps.agents.troubleshooting_service_agent.build_llm', return_value=llm):
            orchestrator = StubOrchestrator()
            chunks = list(
                orchestrator.run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='Please send a technician — machine keeps stopping',
                    session_id='session-1',
                ),
            )

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('create_ticket', tool_names)

        ticket_chunk = next(c for c in chunks if c.tool == 'create_ticket')
        self.assertIsNotNone(ticket_chunk.data)
        assert ticket_chunk.data is not None
        self.assertEqual(ticket_chunk.data['status'], 'ok')
        self.assertTrue(ticket_chunk.data['data']['ticket_id'].startswith('TKT-'))

    def test_cross_tenant_machine_lookup_halts_before_any_llm_call(self) -> None:
        # No llm patch -- scoping must fail before the tool-calling loop
        # ever starts, so the (unpatched, real) ChatAnthropic is never built.
        orchestrator = StubOrchestrator()
        chunks = list(
            orchestrator.run(
                customer_id='someone-else',
                machine_serial='A3279',
                message='Alarm E042',
                session_id='session-1',
            ),
        )
        self.assertEqual([c.type for c in chunks], ['step', 'tool', 'error', 'done'])


class LangGraphOrchestratorTests(TransactionTestCase):
    """TransactionTestCase, not TestCase: LangGraph dispatches node execution
    on worker threads, and TestCase's single-connection-in-a-transaction
    SQLite isolation deadlocks ("database is locked") when a node's DB query
    runs on a different thread/connection than the one holding the test's
    open transaction. TransactionTestCase avoids the wrapping transaction."""

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        _make_machine(self.user)

    def test_classify_intent(self) -> None:
        self.assertEqual(
            classify_intent('Has our quote been revised?'),
            AgentIntent.ORDERS_BUSINESS,
        )
        self.assertEqual(
            classify_intent('What is the status of my last order?'),
            AgentIntent.ORDERS_BUSINESS,
        )
        self.assertEqual(
            classify_intent('Alarm E042 star-wheel jam'),
            AgentIntent.TROUBLESHOOTING_SERVICE,
        )
        self.assertEqual(
            classify_intent('What machine is this?'),
            AgentIntent.TROUBLESHOOTING_SERVICE,
        )

    def test_routes_business_message_to_orders_business_agent(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn('get_order_status', {}),
                _text_turn('Your order has shipped.'),
            ],
        )
        with patch('apps.agents.orders_business_agent.build_llm', return_value=llm):
            chunks = list(
                LangGraphOrchestrator().run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='What is the status of my order?',
                    session_id='session-1',
                ),
            )

        step_labels = [c.content for c in chunks if c.type == 'step']
        self.assertTrue(any('Orders/Business' in s for s in step_labels))

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('get_order_status', tool_names)
        self.assertEqual(chunks[-1].type, 'done')

    def test_routes_troubleshooting_message_to_troubleshooting_service_agent(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn('search_error_codes', {'query': 'E042'}),
                _text_turn('That alarm means a star-wheel jam.'),
            ],
        )
        with patch('apps.agents.troubleshooting_service_agent.build_llm', return_value=llm):
            chunks = list(
                LangGraphOrchestrator().run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='Alarm E042 star-wheel jam',
                    session_id='session-1',
                ),
            )

        step_labels = [c.content for c in chunks if c.type == 'step']
        self.assertTrue(any('Troubleshooting/Service' in s for s in step_labels))

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('search_error_codes', tool_names)
        self.assertEqual(chunks[-1].type, 'done')

    def test_second_turn_on_same_session_sees_first_turns_history(self) -> None:
        """The book's Chapter 2 point: state must carry across turns, not be
        discarded when a run() generator finishes. Here the *second* call's
        scripted LLM never gets a tool_call turn -- if the graph's checkpointed
        `messages` didn't include the first turn's exchange, the fake model
        would still return exactly what we scripted (it doesn't read
        messages), so the real assertion is on what we fed IT: intercept
        llm.stream(messages) and check the first turn's Human/AI messages
        are present on the second call.
        """
        seen_message_histories: list[list] = []

        class _RecordingScriptedLLM(_ScriptedLLM):
            def stream(self, messages):
                seen_message_histories.append(list(messages))
                yield from super().stream(messages)

        llm = _RecordingScriptedLLM(
            [
                _tool_call_turn('search_error_codes', {'query': 'E042'}),
                _text_turn('That alarm means a star-wheel jam.'),
                _text_turn('Yes, clearing the jam and resetting the alarm should fix it.'),
            ],
        )
        with patch('apps.agents.troubleshooting_service_agent.build_llm', return_value=llm):
            list(
                LangGraphOrchestrator().run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='Alarm E042 star-wheel jam',
                    session_id='session-continuity',
                ),
            )
            list(
                LangGraphOrchestrator().run(
                    customer_id='demo',
                    machine_serial='A3279',
                    message='Will that actually fix it?',
                    session_id='session-continuity',
                ),
            )

        # Third llm.stream() call is the second turn's only round-trip
        # (the scripted answer has no tool call). Its message list must
        # contain the first turn's human message and final answer, proving
        # history survived across the two separate run() calls.
        second_turn_messages = seen_message_histories[2]
        history_texts = [getattr(m, 'content', '') for m in second_turn_messages]
        self.assertTrue(any('Alarm E042 star-wheel jam' in t for t in history_texts))
        self.assertTrue(any('star-wheel jam' in t and 'That alarm means' in t for t in history_texts))
        self.assertTrue(any('Will that actually fix it?' in t for t in history_texts))


class ChatViewTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        _make_machine(self.user)
        self.client = Client()

    def test_chat_requires_auth(self) -> None:
        response = self.client.post(
            '/api/agents/chat/',
            data={'message': 'hello'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(ORCHESTRATOR_BACKEND='stub')
    def test_chat_streams_sse_for_authenticated_user(self) -> None:
        llm = _ScriptedLLM([_text_turn('This is a CLOSYS EAGLE VP capping machine.')])
        self.client.login(username='demo', password='demo')
        with patch('apps.agents.troubleshooting_service_agent.build_llm', return_value=llm):
            response = self.client.post(
                '/api/agents/chat/',
                data={'message': 'What machine is this?', 'machine_serial': 'A3279'},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('"type": "token"', body)
        self.assertIn('"type": "tool"', body)
        self.assertIn('"type": "step"', body)
        self.assertIn('"type": "done"', body)
