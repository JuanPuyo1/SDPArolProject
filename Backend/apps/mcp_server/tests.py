"""MCP registry, tenant scoping, visibility, and tool behaviour tests."""

from __future__ import annotations

from django.test import Client, TestCase, override_settings

from apps.core.test_fixtures import PASSWORD, seed_spec_fleet
from apps.machines.models import MaintenanceTicket
from apps.mcp_server import registry
from apps.mcp_server.rag_engine.client import reset_client
from apps.mcp_server.scoping import ScopeError, get_owned_machine, resolve_customer


def _use_in_memory_qdrant(test_case: TestCase) -> None:
    reset_client()
    test_case.addCleanup(reset_client)


class McpRegistryCatalogTests(TestCase):
    def test_expected_tools_are_registered(self) -> None:
        names = {t["name"] for t in registry.list_tools()}
        self.assertEqual(
            names,
            {
                "echo",
                "get_machine_info",
                "list_customer_machines",
                "search_manual",
                "query_telemetry",
                "list_spare_parts",
                "search_error_codes",
                "list_alarms",
                "create_ticket",
                "list_maintenance_tickets",
                "get_quote_history",
                "get_order_status",
            },
        )

    def test_stub_vs_ready_status_follows_output_schema(self) -> None:
        by_name = {t["name"]: t for t in registry.list_tools()}
        self.assertEqual(by_name["create_ticket"]["status"], "stub")
        self.assertEqual(by_name["list_spare_parts"]["status"], "stub")
        self.assertEqual(by_name["get_machine_info"]["status"], "ready")
        self.assertEqual(by_name["query_telemetry"]["status"], "ready")
        self.assertEqual(by_name["get_quote_history"]["status"], "ready")

    def test_unknown_tool_returns_structured_error(self) -> None:
        result = registry.invoke("does_not_exist", {})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "UNKNOWN_TOOL")

    def test_validation_error_for_missing_scope(self) -> None:
        result = registry.invoke("get_machine_info", {})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "VALIDATION_ERROR")


class ScopingTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_resolve_customer_accepts_username_and_user_id(self) -> None:
        by_username = resolve_customer("acme_full")
        by_user_id = resolve_customer("USR-ACME-FULL")
        self.assertEqual(by_username.pk, by_user_id.pk)

    def test_unknown_customer_is_not_found(self) -> None:
        with self.assertRaises(ScopeError) as ctx:
            resolve_customer("no-such-user")
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_owned_machine_is_returned(self) -> None:
        machine = get_owned_machine(customer_id="acme_full", machine_serial="17478")
        self.assertEqual(machine.machine_id, "MCH-0004")

    def test_foreign_machine_is_forbidden(self) -> None:
        with self.assertRaises(ScopeError) as ctx:
            get_owned_machine(customer_id="acme_full", machine_serial="99999")
        self.assertEqual(ctx.exception.code, "FORBIDDEN")

    def test_unknown_serial_is_not_found(self) -> None:
        with self.assertRaises(ScopeError) as ctx:
            get_owned_machine(customer_id="acme_full", machine_serial="NOPE")
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


class McpTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_get_machine_info_ok_for_owner(self) -> None:
        result = registry.invoke(
            "get_machine_info",
            {"customer_id": "acme_full", "machine_serial": "17478"},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["machine"]["serialNumber"], "17478")
        self.assertEqual(result["data"]["machine"]["company"]["companyId"], "CMP-ACME")

    def test_get_machine_info_forbids_cross_tenant(self) -> None:
        result = registry.invoke(
            "get_machine_info",
            {"customer_id": "acme_full", "machine_serial": "99999"},
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "FORBIDDEN")

    def test_list_customer_machines_never_crosses_company(self) -> None:
        result = registry.invoke(
            "list_customer_machines",
            {"customer_id": "acme_full"},
        )
        serials = {m["serial_number"] for m in result["data"]["machines"]}
        self.assertEqual(serials, {"17478", "A3279"})

    def test_list_customer_machines_empty_company_is_empty_not_error(self) -> None:
        result = registry.invoke(
            "list_customer_machines",
            {"customer_id": "empty_user"},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["machines"], [])

    def test_list_alarms_does_not_include_foreign_machine(self) -> None:
        result = registry.invoke(
            "list_alarms",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "active_only": False,
            },
        )
        self.assertEqual(result["status"], "ok")
        ids = {a["alarm_id"] for a in result["data"]["alarms"]}
        self.assertIn("ALM-OPEN", ids)
        self.assertNotIn("ALM-FOREIGN", ids)


class McpVisibilityTests(TestCase):
    """Access Model: both companyId and visibility must pass."""

    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_technician_can_query_operational_tools(self) -> None:
        for tool, extra in (
            ("query_telemetry", {"metric": "temperature"}),
            ("list_alarms", {}),
            ("list_maintenance_tickets", {}),
        ):
            result = registry.invoke(
                tool,
                {"customer_id": "acme_tech", "machine_serial": "17478", **extra},
            )
            self.assertEqual(result["status"], "ok", result)

    def test_technician_is_forbidden_from_commercial_tools(self) -> None:
        for tool, extra in (
            ("get_quote_history", {}),
            ("get_order_status", {}),
            ("list_spare_parts", {"query": "capping head"}),
        ):
            result = registry.invoke(
                tool,
                {"customer_id": "acme_tech", "machine_serial": "17478", **extra},
            )
            self.assertEqual(result["status"], "error", tool)
            self.assertEqual(result["code"], "FORBIDDEN", tool)
            self.assertIn("cannot use", result["message"])

    def test_commercial_can_query_commercial_tools(self) -> None:
        for tool, extra in (
            ("get_quote_history", {}),
            ("get_order_status", {}),
        ):
            result = registry.invoke(
                tool,
                {"customer_id": "acme_comm", "machine_serial": "17478", **extra},
            )
            self.assertEqual(result["status"], "ok", result)

    def test_commercial_is_forbidden_from_operational_tools(self) -> None:
        for tool, extra in (
            ("query_telemetry", {"metric": "temperature"}),
            ("list_alarms", {}),
            ("list_maintenance_tickets", {}),
            ("search_error_codes", {"query": "AL017"}),
            ("create_ticket", {"subject": "Need help", "description": "Please send a technician"}),
        ):
            result = registry.invoke(
                tool,
                {"customer_id": "acme_comm", "machine_serial": "17478", **extra},
            )
            self.assertEqual(result["status"], "error", tool)
            self.assertEqual(result["code"], "FORBIDDEN", tool)

    def test_all_roles_can_read_machine_identity(self) -> None:
        for username in ("acme_full", "acme_tech", "acme_comm"):
            result = registry.invoke(
                "get_machine_info",
                {"customer_id": username, "machine_serial": "17478"},
            )
            self.assertEqual(result["status"], "ok", username)


class TelemetryToolTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_query_temperature_points(self) -> None:
        result = registry.invoke(
            "query_telemetry",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "metric": "temperature",
            },
        )
        self.assertEqual(result["status"], "ok")
        points = result["data"]["points"]
        self.assertGreaterEqual(len(points), 2)
        self.assertEqual(points[0]["unit"], "°C")

    def test_idle_interval_has_zero_production_rate(self) -> None:
        result = registry.invoke(
            "query_telemetry",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "metric": "production_rate_bph",
            },
        )
        values = {p["value"] for p in result["data"]["points"]}
        self.assertIn(0.0, values)
        self.assertIn(18000.0, values)

    def test_time_window_filters_snapshots(self) -> None:
        from apps.machines.models import TelemetrySnapshot

        running = TelemetrySnapshot.objects.get(telemetry_id="TEL-RUN")
        result = registry.invoke(
            "query_telemetry",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "metric": "temperature",
                "from_ts": running.timestamp.isoformat(),
            },
        )
        self.assertEqual(len(result["data"]["points"]), 1)


class AlarmAndTicketToolTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_list_alarms_defaults_to_active_only(self) -> None:
        result = registry.invoke(
            "list_alarms",
            {"customer_id": "acme_full", "machine_serial": "17478"},
        )
        ids = {a["alarm_id"] for a in result["data"]["alarms"]}
        self.assertEqual(ids, {"ALM-OPEN"})

    def test_list_alarms_full_history_includes_resolved(self) -> None:
        result = registry.invoke(
            "list_alarms",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "active_only": False,
            },
        )
        ids = {a["alarm_id"] for a in result["data"]["alarms"]}
        self.assertEqual(ids, {"ALM-OPEN", "ALM-RES"})
        codes = {a["alarm_code"] for a in result["data"]["alarms"]}
        self.assertIn("AL017_LOW_AIR_PRESSURE", codes)

    def test_list_maintenance_tickets_keeps_null_alarm(self) -> None:
        result = registry.invoke(
            "list_maintenance_tickets",
            {"customer_id": "acme_full", "machine_serial": "17478"},
        )
        by_id = {t["ticket_id"]: t for t in result["data"]["tickets"]}
        self.assertIsNone(by_id["TKT-NO-ALM"]["alarm_id"])
        self.assertEqual(by_id["TKT-FROM-ALM"]["alarm_id"], "ALM-OPEN")

    def test_create_ticket_is_stub_and_does_not_persist(self) -> None:
        before = MaintenanceTicket.objects.filter(machine=self.fleet.machine).count()
        result = registry.invoke(
            "create_ticket",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "subject": "Machine keeps stopping",
                "description": "Please send a technician",
                "priority": "high",
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["ticket_id"].startswith("TKT-"))
        self.assertTrue(result["data"]["stub"])
        self.assertEqual(
            MaintenanceTicket.objects.filter(machine=self.fleet.machine).count(),
            before,
        )


class QuoteOrderToolTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_quote_history_returns_all_revisions_oldest_to_newest(self) -> None:
        result = registry.invoke(
            "get_quote_history",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "quote_id": "QUO-SPEC-1",
            },
        )
        self.assertEqual(result["status"], "ok")
        revisions = result["data"]["revisions"]
        self.assertEqual([r["revision_number"] for r in revisions], [1, 2])
        self.assertEqual(revisions[0]["status"], "Superseded")
        self.assertEqual(revisions[1]["status"], "Approved")
        self.assertEqual(revisions[1]["amount_eur"], 9000.0)

    def test_order_status_includes_confirmed_orders(self) -> None:
        result = registry.invoke(
            "get_order_status",
            {"customer_id": "acme_full", "machine_serial": "17478"},
        )
        ids = {o["order_id"] for o in result["data"]["orders"]}
        self.assertIn("ORD-SPEC-1", ids)


class EchoAndHttpDebugTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()

    def test_echo_round_trip(self) -> None:
        result = registry.invoke(
            "echo",
            {
                "message": "ping",
                "customer_id": "acme_full",
                "machine_serial": "17478",
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["echo"], "ping")

    def test_http_invoke_forbids_cross_tenant(self) -> None:
        response = self.client.post(
            "/api/mcp/tools/get_machine_info/invoke/",
            data={
                "customer_id": "acme_full",
                "machine_serial": "99999",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "FORBIDDEN")

    def test_http_list_tools(self) -> None:
        response = self.client.get("/api/mcp/tools/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["tools"]), 10)


@override_settings(QDRANT_URL=":memory:")
class RagManualSearchTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        _use_in_memory_qdrant(self)

    def test_search_manual_requires_owned_machine(self) -> None:
        result = registry.invoke(
            "search_manual",
            {
                "customer_id": "acme_full",
                "machine_serial": "99999",
                "query": "air pressure",
            },
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "FORBIDDEN")

    def test_markdown_ingestion_and_payload_consistency(self) -> None:
        from apps.mcp_server.rag_engine import search as rag_search
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

        sample_md = """<!-- Page 10 -->

# CHAPTER 5: MAINTENANCE

## Section 5.2 - Capping Head Pressure

To adjust capping head pressure on CLOSYS EAGLE VP, turn calibration screw T-804 clockwise.
"""
        count = ingest_markdown_text(
            markdown_text=sample_md,
            metadata=IngestMetadata(
                machine_serial="17478",
                doc_id="test-doc-01",
                doc_type="user_manual",
                source="17478_manual_EN.pdf",
            ),
        )
        self.assertGreater(count, 0)

        hits = rag_search.search_manuals(
            query="calibration screw T-804 pressure",
            machine_serial="17478",
            top_k=2,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["page_number"], 10)

    def test_search_manual_mcp_tool_returns_hits(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

        ingest_markdown_text(
            markdown_text="""<!-- Page 14 -->

# CHAPTER 3: OPERATING MODES

## Section 3.1 - Operator Safety

Always press emergency stop button before clearing bottle jam.
""",
            metadata=IngestMetadata(
                machine_serial="17478",
                doc_id="safety-doc",
                doc_type="user_manual",
                source="17478_manual_EN.pdf",
            ),
        )
        result = registry.invoke(
            "search_manual",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "query": "emergency stop button bottle jam",
                "top_k": 3,
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(len(result["data"]["hits"]), 1)
        self.assertEqual(result["data"]["hits"][0]["page_number"], 14)

    def test_search_does_not_return_another_machines_exclusive_manual(self) -> None:
        """Manuals are machine-specific. Unfiltered fallback must not leak."""
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

        ingest_markdown_text(
            markdown_text="""<!-- Page 3 -->

# FOREIGN MACHINE ONLY

Secret remedy for AL017 on serial 99999: replace the foreign-only valve FV-99.
""",
            metadata=IngestMetadata(
                machine_serial="99999",
                doc_id="foreign-doc",
                doc_type="user_manual",
                source="99999_manual_EN.pdf",
            ),
        )
        result = registry.invoke(
            "search_manual",
            {
                "customer_id": "acme_full",
                "machine_serial": "17478",
                "query": "foreign-only valve FV-99",
                "top_k": 3,
            },
        )
        self.assertEqual(result["status"], "ok")
        excerpts = " ".join(h["excerpt"] for h in result["data"]["hits"])
        self.assertNotIn("FV-99", excerpts)
