"""Tests for chat SSE endpoint, stub/langgraph orchestrators, and routing.

These tests never hit the real Claude API. Instead they inject a small
scripted fake in place of the LLM (see _ScriptedLLM below) so the tests stay
fast/deterministic and verify our own plumbing -- tool-calling loop,
tenant scoping, chunk sequencing -- rather than Claude's actual reasoning.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool

from apps.agents.agent_kit import AgentTool, mcp_tool, run_tool_calling_loop
from apps.agents.langgraph_orchestrator import (
    AgentIntent,
    LangGraphOrchestrator,
    classify_intent,
)
from apps.agents.stub_orchestrator import StubOrchestrator
from apps.agents.telemetry_agent import TelemetryAgent
from datetime import date

from apps.core.models import Company
from apps.machines.models import Machine, MachineModel
from apps.machines.models import Machine
from apps.mcp_server import registry


def _tool_call_turn(
    name: str, args: dict, call_id: str = "call_1"
) -> list[AIMessageChunk]:
    """One streamed turn: a single delta carrying a complete tool call."""
    return [
        AIMessageChunk(
            content="",
            tool_calls=[
                {"name": name, "args": args, "id": call_id, "type": "tool_call"}
            ],
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


class _FakeRouterLLM:
    """Router stand-in: classify_intent() only ever calls .invoke(messages)
    and reads the returned object's `.agent` attribute -- matches the shape
    of the real _RouteDecision structured-output result without hitting
    Claude, so routing tests stay deterministic and don't test the model's
    actual judgement (see module docstring)."""

    def __init__(self, agent: str) -> None:
        self._agent = agent

    def invoke(self, _messages):
        return SimpleNamespace(agent=self._agent)


def _make_machine(owner) -> Machine:
    company = owner.company
    if company is None:
        company = Company.objects.create(
            company_id=f"CMP-{owner.username.upper()}",
            company_name=f"{owner.username} Co",
            country="Italy",
            sector="Beverage",
            city="Novara",
            currency="EUR",
            locale="it-IT",
        )
        owner.company = company
        owner.save(update_fields=["company"])

    machine_model, _ = MachineModel.objects.get_or_create(
        model_id="MDL-AGENT-TEST",
        defaults={
            "model_code": "CLOSYS EAGLE VP",
            "description": "Test machine",
            "nominal_heads": 1,
            "container_type": "PET bottles",
            "cap_type": "Plastic screw cap",
            "industry_segment": "Beverage",
        },
    )
    return Machine.objects.create(
        machine_id=f"MCH-{owner.username.upper()}",
        company=company,
        model=machine_model,
        serial_number="A3279",
        delivery_date=date(2014, 1, 1),
        plant_location="Test Plant",
        configuration_profile="Test config",
        plc_family="SIEMENS-SIMATIC-S7",
    )


class RunToolCallingLoopTests(TestCase):
    """Circuit-breaker behavior of run_tool_calling_loop itself: a
    hallucinated tool name or a raising tool must become an error fed back to
    the model, never an uncaught exception, and a model that keeps calling
    tools forever must be cut off rather than looping (and billing) forever."""

    def test_unknown_tool_call_is_reported_to_model_not_raised(self) -> None:
        @tool
        def noop_tool() -> dict:
            """Does nothing."""
            return {"status": "ok"}

        llm = _ScriptedLLM(
            [
                _tool_call_turn("does_not_exist", {}),
                _text_turn("Sorry, I could not find that tool."),
            ],
        )
        chunks = list(
            run_tool_calling_loop(
                llm,
                [AgentTool(noop_tool, "Doing nothing…")],
                system_prompt="test",
                user_message="hi",
            ),
        )

        tool_chunk = next(c for c in chunks if c.type == "tool")
        self.assertEqual(tool_chunk.tool, "does_not_exist")
        assert tool_chunk.data is not None
        self.assertEqual(tool_chunk.data["status"], "error")
        self.assertIn("Unknown tool", tool_chunk.data["message"])
        # The loop recovered and still produced a final answer instead of
        # crashing on the KeyError that `tools_by_name[call['name']]` used to
        # raise for a hallucinated tool name.
        self.assertTrue(any(c.type == "token" for c in chunks))

    def test_tool_exception_is_reported_to_model_not_raised(self) -> None:
        @tool
        def boom_tool() -> dict:
            """Always raises."""
            raise RuntimeError("kaboom")

        llm = _ScriptedLLM(
            [
                _tool_call_turn("boom_tool", {}),
                _text_turn("The tool failed, here is what happened."),
            ],
        )
        chunks = list(
            run_tool_calling_loop(
                llm,
                [AgentTool(boom_tool, "Triggering boom…")],
                system_prompt="test",
                user_message="hi",
            ),
        )

        tool_chunk = next(c for c in chunks if c.type == "tool")
        assert tool_chunk.data is not None
        self.assertEqual(tool_chunk.data["status"], "error")
        self.assertIn("kaboom", tool_chunk.data["message"])
        self.assertTrue(any(c.type == "token" for c in chunks))

    def test_max_iterations_cap_stops_an_infinite_tool_loop(self) -> None:
        @tool
        def spin_tool() -> dict:
            """A tool a runaway model keeps calling instead of answering."""
            return {"status": "ok"}

        # Every scripted turn calls the tool again -- with no cap this would
        # be `while True:` and never terminate.
        llm = _ScriptedLLM([_tool_call_turn("spin_tool", {}) for _ in range(3)])
        chunks = list(
            run_tool_calling_loop(
                llm,
                [AgentTool(spin_tool, "Spinning…")],
                system_prompt="test",
                user_message="hi",
                max_iterations=3,
            ),
        )

        tool_chunks = [c for c in chunks if c.type == "tool"]
        self.assertEqual(len(tool_chunks), 3)
        self.assertEqual(chunks[-1].type, "error")
        assert chunks[-1].message is not None
        self.assertIn("3 tool-calling round-trips", chunks[-1].message)


class BuildAgentToolsTests(TestCase):
    """Regression coverage for the description-drift fix: a tool's name,
    description, and argument schema must come from its registry.py
    ToolSpec -- the single source of truth -- not a hand-copied `@tool`
    docstring per agent that can silently go stale. No DB fixture needed:
    building a tool's schema doesn't invoke it (that's where tenant scoping
    is checked), so these never touch scoping.get_owned_machine."""

    def test_tool_description_matches_registry_not_a_hand_copied_docstring(
        self,
    ) -> None:
        built = mcp_tool(
            "get_quote_history", customer_id="demo", machine_serial="A3279"
        )
        spec = registry.get_tool("get_quote_history")
        assert spec is not None
        self.assertEqual(built.tool.description, spec.description)

    def test_scope_fields_are_stripped_from_the_llm_visible_schema(self) -> None:
        built = mcp_tool(
            "get_quote_history", customer_id="demo", machine_serial="A3279"
        )
        fields = built.tool.args_schema.model_fields
        self.assertNotIn("customer_id", fields)
        self.assertNotIn("machine_serial", fields)
        self.assertIn("quote_id", fields)
        self.assertIn("target_machine_serial", fields)

    def test_unscoped_tools_do_not_expose_target_serial(self) -> None:
        built = mcp_tool(
            "list_customer_machines", customer_id="demo", machine_serial="A3279"
        )
        fields = built.tool.args_schema.model_fields
        self.assertNotIn("customer_id", fields)
        self.assertNotIn("machine_serial", fields)
        self.assertNotIn("target_machine_serial", fields)

    def test_unknown_tool_name_raises_at_build_time_not_silently(self) -> None:
        with self.assertRaises(ValueError):
            mcp_tool("does_not_exist", customer_id="demo", machine_serial="A3279")

    def test_orders_business_agent_picks_up_every_business_tagged_tool(self) -> None:
        from apps.agents.orders_business_agent import _build_tools

        names = {t.tool.name for t in _build_tools("demo", "A3279")}
        self.assertEqual(
            names,
            {
                "get_quote_history",
                "get_order_status",
                "list_spare_parts",
                "list_customer_machines",
            },
        )

    def test_troubleshooting_agent_spans_its_two_registry_domains_only(self) -> None:
        from apps.agents.troubleshooting_service_agent import _build_tools

        names = {t.tool.name for t in _build_tools("demo", "A3279")}
        self.assertEqual(
            names,
            {
                "search_error_codes",
                "list_alarms",
                "create_ticket",
                "list_maintenance_tickets",
                "list_customer_machines",
            },
        )
        # 'shared' tools (get_machine_info, echo, ...) must not leak in even
        # though list_tools(agent=X) also returns them as a discovery aid.
        self.assertNotIn("get_machine_info", names)

    def test_telemetry_agent_picks_up_query_telemetry_and_fleet_lookup(self) -> None:
        from apps.agents.telemetry_agent import _build_tools

        names = {t.tool.name for t in _build_tools("demo", "A3279")}
        self.assertEqual(names, {"query_telemetry", "list_customer_machines"})

    def test_manuals_agent_owns_search_manual_only(self) -> None:
        from apps.agents.manuals_agent import _build_tools

        names = {t.tool.name for t in _build_tools("demo", "A3279")}
        self.assertEqual(names, {"search_manual", "list_customer_machines"})


class McpToolTargetSerialTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username="demo", password="demo")
        self.machine = _make_machine(self.user)
        Machine.objects.create(
            machine_id="MCH-DEMO2",
            company=self.user.company,
            model=self.machine.model,
            serial_number="17478",
            delivery_date=date(2019, 7, 22),
            plant_location="Line 2",
            configuration_profile="Test config 2",
            plc_family="SIEMENS-SIMATIC-S7",
        )
        other_company = Company.objects.create(
            company_id="CMP-OTHER-AGENT",
            company_name="Other Co",
            country="France",
            sector="Spirits",
            city="Saintes",
            currency="EUR",
            locale="fr-FR",
        )
        Machine.objects.create(
            machine_id="MCH-FOREIGN",
            company=other_company,
            model=self.machine.model,
            serial_number="FOREIGN1",
            delivery_date=date(2018, 1, 1),
            plant_location="Other plant",
            configuration_profile="Foreign config",
            plc_family="SIEMENS-SIMATIC-S7",
        )

    def test_target_serial_of_owned_machine_is_used(self) -> None:
        built = mcp_tool(
            "get_machine_info", customer_id="demo", machine_serial="A3279"
        )
        result = built.tool.invoke({"target_machine_serial": "17478"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["machine"]["serialNumber"], "17478")

    def test_target_serial_of_unowned_machine_is_forbidden(self) -> None:
        built = mcp_tool(
            "get_machine_info", customer_id="demo", machine_serial="A3279"
        )
        result = built.tool.invoke({"target_machine_serial": "FOREIGN1"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "FORBIDDEN")


class StubOrchestratorTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username="demo", password="demo")
        _make_machine(self.user)

    def test_stub_calls_mcp_tools_and_streams_final_answer(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn("search_manual", {"query": "E042 star-wheel jam"}),
                _text_turn(
                    "Error E042 indicates a star-wheel jam. Clear the jam and reset the alarm."
                ),
            ],
        )
        with patch(
            "apps.agents.troubleshooting_service_agent.build_llm", return_value=llm
        ):
            orchestrator = StubOrchestrator()
            chunks = list(
                orchestrator.run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="Alarm E042 star-wheel jam",
                    session_id="session-1",
                ),
            )

        types = [c.type for c in chunks]
        self.assertIn("step", types)
        self.assertIn("tool", types)
        self.assertIn("token", types)
        self.assertEqual(types[-1], "done")

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("get_machine_info", tool_names)
        self.assertIn("search_manual", tool_names)

        # get_machine_info's result is real (not scripted) -- confirms the
        # actual scoping/registry call ran, not just the fake narration.
        machine_chunk = next(c for c in chunks if c.tool == "get_machine_info")
        self.assertIsNotNone(machine_chunk.data)
        assert machine_chunk.data is not None
        self.assertEqual(machine_chunk.data["data"]["machine"]["serialNumber"], "A3279")

        text = "".join(c.content for c in chunks if c.type == "token")
        self.assertIn("star-wheel jam", text)

    def test_service_intent_opens_ticket(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn(
                    "create_ticket",
                    {
                        "subject": "Machine keeps stopping",
                        "description": "Please send a technician — machine keeps stopping",
                        "priority": "high",
                        "category": "support",
                    },
                ),
                _text_turn("A field-support ticket has been opened for you."),
            ],
        )
        with patch(
            "apps.agents.troubleshooting_service_agent.build_llm", return_value=llm
        ):
            orchestrator = StubOrchestrator()
            chunks = list(
                orchestrator.run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="Please send a technician — machine keeps stopping",
                    session_id="session-1",
                ),
            )

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("create_ticket", tool_names)

        ticket_chunk = next(c for c in chunks if c.tool == "create_ticket")
        self.assertIsNotNone(ticket_chunk.data)
        assert ticket_chunk.data is not None
        self.assertEqual(ticket_chunk.data["status"], "ok")
        self.assertTrue(ticket_chunk.data["data"]["ticket_id"].startswith("TKT-"))

    def test_cross_tenant_machine_lookup_halts_before_any_llm_call(self) -> None:
        # No llm patch -- scoping must fail before the tool-calling loop
        # ever starts, so the (unpatched, real) ChatAnthropic is never built.
        orchestrator = StubOrchestrator()
        chunks = list(
            orchestrator.run(
                customer_id="someone-else",
                machine_serial="A3279",
                message="Alarm E042",
                session_id="session-1",
            ),
        )
        self.assertEqual([c.type for c in chunks], ["step", "tool", "error", "done"])


class LangGraphOrchestratorTests(TransactionTestCase):
    """TransactionTestCase, not TestCase: LangGraph dispatches node execution
    on worker threads, and TestCase's single-connection-in-a-transaction
    SQLite isolation deadlocks ("database is locked") when a node's DB query
    runs on a different thread/connection than the one holding the test's
    open transaction. TransactionTestCase avoids the wrapping transaction."""

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username="demo", password="demo")
        _make_machine(self.user)

    def test_classify_intent_maps_router_decision_to_agent_intent(self) -> None:
        """classify_intent() is now a thin wrapper around an LLM structured-
        output call (see langgraph_orchestrator.build_router_llm) rather than
        a keyword regex, so this only verifies the plumbing -- that the
        message reaches the router and its `.agent` decision maps onto the
        right AgentIntent -- not the model's actual judgement."""
        seen_messages: list[list] = []

        class _RecordingRouterLLM(_FakeRouterLLM):
            def invoke(self, messages):
                seen_messages.append(list(messages))
                return super().invoke(messages)

        self.assertEqual(
            classify_intent(
                "Has our quote been revised?",
                llm=_RecordingRouterLLM("orders_business"),
            ),
            AgentIntent.ORDERS_BUSINESS,
        )
        self.assertEqual(
            classify_intent(
                "Alarm E042 star-wheel jam",
                llm=_RecordingRouterLLM("troubleshooting_service"),
            ),
            AgentIntent.TROUBLESHOOTING_SERVICE,
        )
        self.assertEqual(
            classify_intent(
                "How do I adjust torque on the capping head?",
                llm=_RecordingRouterLLM("manuals"),
            ),
            AgentIntent.MANUALS,
        )

        last_call_texts = [getattr(m, "content", "") for m in seen_messages[-1]]
        self.assertTrue(
            any("adjust torque on the capping head" in t for t in last_call_texts)
        )

    def test_routes_business_message_to_orders_business_agent(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn("get_order_status", {}),
                _text_turn("Your order has shipped."),
            ],
        )
        with (
            patch(
                "apps.agents.langgraph_orchestrator.build_router_llm",
                return_value=_FakeRouterLLM("orders_business"),
            ),
            patch("apps.agents.orders_business_agent.build_llm", return_value=llm),
        ):
            chunks = list(
                LangGraphOrchestrator().run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="What is the status of my order?",
                    session_id="session-1",
                ),
            )

        step_labels = [c.content for c in chunks if c.type == "step"]
        self.assertTrue(any("Orders/Business" in s for s in step_labels))
        router_step = next(c for c in chunks if c.type == "step" and c.agent)
        self.assertEqual(router_step.agent, "orders_business")

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("get_order_status", tool_names)
        self.assertEqual(chunks[-1].type, "done")

    def test_routes_troubleshooting_message_to_troubleshooting_service_agent(
        self,
    ) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn("search_manual", {"query": "E042"}),
                _text_turn("That alarm means a star-wheel jam."),
            ],
        )
        with (
            patch(
                "apps.agents.langgraph_orchestrator.build_router_llm",
                return_value=_FakeRouterLLM("troubleshooting_service"),
            ),
            patch(
                "apps.agents.troubleshooting_service_agent.build_llm", return_value=llm
            ),
        ):
            chunks = list(
                LangGraphOrchestrator().run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="Alarm E042 star-wheel jam",
                    session_id="session-1",
                ),
            )

        step_labels = [c.content for c in chunks if c.type == "step"]
        self.assertTrue(any("Troubleshooting/Service" in s for s in step_labels))
        router_step = next(c for c in chunks if c.type == "step" and c.agent)
        self.assertEqual(router_step.agent, "troubleshooting_service")

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("search_manual", tool_names)
        self.assertEqual(chunks[-1].type, "done")

    def test_routes_manual_message_to_manuals_agent(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn(
                    "search_manual", {"query": "torque adjustment capping head"}
                ),
                _text_turn("Section 4.2 covers torque adjustment on the capping head."),
            ],
        )
        with (
            patch(
                "apps.agents.langgraph_orchestrator.build_router_llm",
                return_value=_FakeRouterLLM("manuals"),
            ),
            patch("apps.agents.manuals_agent.build_llm", return_value=llm),
        ):
            chunks = list(
                LangGraphOrchestrator().run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="How do I adjust torque on the capping head?",
                    session_id="session-1",
                ),
            )

        step_labels = [c.content for c in chunks if c.type == "step"]
        self.assertTrue(any("Manuals" in s for s in step_labels))
        router_step = next(c for c in chunks if c.type == "step" and c.agent)
        self.assertEqual(router_step.agent, "manuals")

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("search_manual", tool_names)
        self.assertEqual(chunks[-1].type, "done")

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
                _tool_call_turn("search_manual", {"query": "E042"}),
                _text_turn("That alarm means a star-wheel jam."),
                _text_turn(
                    "Yes, clearing the jam and resetting the alarm should fix it."
                ),
            ],
        )
        with (
            patch(
                "apps.agents.langgraph_orchestrator.build_router_llm",
                return_value=_FakeRouterLLM("troubleshooting_service"),
            ),
            patch(
                "apps.agents.troubleshooting_service_agent.build_llm", return_value=llm
            ),
        ):
            list(
                LangGraphOrchestrator().run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="Alarm E042 star-wheel jam",
                    session_id="session-continuity",
                ),
            )
            list(
                LangGraphOrchestrator().run(
                    customer_id="demo",
                    machine_serial="A3279",
                    message="Will that actually fix it?",
                    session_id="session-continuity",
                ),
            )

        # Third llm.stream() call is the second turn's only round-trip
        # (the scripted answer has no tool call). Its message list must
        # contain the first turn's human message and final answer, proving
        # history survived across the two separate run() calls.
        second_turn_messages = seen_message_histories[2]
        history_texts = [getattr(m, "content", "") for m in second_turn_messages]
        self.assertTrue(any("Alarm E042 star-wheel jam" in t for t in history_texts))
        self.assertTrue(
            any(
                "star-wheel jam" in t and "That alarm means" in t for t in history_texts
            )
        )
        self.assertTrue(any("Will that actually fix it?" in t for t in history_texts))


class ChatViewTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username="demo", password="demo")
        _make_machine(self.user)
        self.client = Client()

    def test_chat_requires_auth(self) -> None:
        response = self.client.post(
            "/api/agents/chat/",
            data={"message": "hello"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(ORCHESTRATOR_BACKEND="stub")
    def test_chat_streams_sse_for_authenticated_user(self) -> None:
        llm = _ScriptedLLM([_text_turn("This is a CLOSYS EAGLE VP capping machine.")])
        self.client.login(username="demo", password="demo")
        with patch(
            "apps.agents.troubleshooting_service_agent.build_llm", return_value=llm
        ):
            response = self.client.post(
                "/api/agents/chat/",
                data={"message": "What machine is this?", "machine_serial": "A3279"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        body = b"".join(response.streaming_content).decode()
        self.assertIn('"type": "token"', body)
        self.assertIn('"type": "tool"', body)
        self.assertIn('"type": "step"', body)
        self.assertIn('"type": "done"', body)


class TelemetryAgentTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username="demo", password="demo")
        _make_machine(self.user)

    def test_telemetry_agent_runs_query_telemetry_tool(self) -> None:
        llm = _ScriptedLLM(
            [
                _tool_call_turn("query_telemetry", {"metric": "temperature"}),
                _text_turn("The average operating temperature is 24°C."),
            ],
        )
        chunks = list(
            TelemetryAgent().run(
                customer_id="demo",
                machine_serial="A3279",
                message="What is the machine temperature?",
                llm=llm,
            ),
        )

        tool_names = [c.tool for c in chunks if c.type == "tool"]
        self.assertIn("get_machine_info", tool_names)
        self.assertIn("query_telemetry", tool_names)

        telemetry_chunk = next(c for c in chunks if c.tool == "query_telemetry")
        self.assertEqual(telemetry_chunk.data["status"], "ok")
        self.assertEqual(telemetry_chunk.data["data"]["metric"], "temperature")

        token_chunks = [c for c in chunks if c.type == "token"]
        full_text = "".join(c.content for c in token_chunks)
        self.assertIn("24°C", full_text)
