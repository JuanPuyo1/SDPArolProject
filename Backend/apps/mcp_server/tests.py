"""Tests for MCP registry + scoped machine tools."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.machines.models import Machine
from apps.mcp_server import registry
from apps.mcp_server.rag_engine.client import reset_client


def _use_in_memory_qdrant(test_case: TestCase) -> None:
    """Point rag_engine's Qdrant client singleton at an isolated in-process
    instance for the duration of one test, instead of the real (shared,
    possibly production) settings.QDRANT_URL.

    get_client() caches its client on first use, so overriding QDRANT_URL
    alone doesn't help once a real client is already cached -- reset_client()
    must run *after* the override takes effect (hence this being called from
    inside the test body, not a class-level decorator) so the next
    get_client() call rebuilds against ':memory:'. Also resets on teardown so
    a later test/process doesn't inherit a client stuck on ':memory:'.
    """
    reset_client()
    test_case.addCleanup(reset_client)


class McpRegistryTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        self.other = User.objects.create_user(username='other', password='other')
        self.machine = Machine.objects.create(
            owner=self.user,
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

    def test_list_tools_includes_core_names(self) -> None:
        names = {t['name'] for t in registry.list_tools()}
        self.assertIn('echo', names)
        self.assertIn('get_machine_info', names)
        self.assertIn('search_manual', names)

    def test_list_tools_agent_filter_includes_shared(self) -> None:
        names = {t['name'] for t in registry.list_tools(agent='manuals')}
        self.assertIn('search_manual', names)
        self.assertIn('get_machine_info', names)
        self.assertNotIn('create_ticket', names)

    def test_echo_ok(self) -> None:
        result = registry.invoke('echo', {'message': 'ping'})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['echo'], 'ping')

    def test_get_machine_info_ok(self) -> None:
        result = registry.invoke(
            'get_machine_info',
            {'customer_id': 'demo', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['machine']['serialNumber'], 'A3279')

    def test_get_machine_info_forbidden_cross_tenant(self) -> None:
        result = registry.invoke(
            'get_machine_info',
            {'customer_id': 'other', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'FORBIDDEN')

    def test_search_manual_returns_hits_for_manual_queries(self) -> None:
        result = registry.invoke(
            'search_manual',
            {
                'customer_id': 'demo',
                'machine_serial': 'A3279',
                'query': 'torque adjustment',
                'top_k': 3,
            },
        )
        self.assertEqual(result['status'], 'ok')
        self.assertGreaterEqual(len(result['data']['hits']), 1)

    def test_list_customer_machines(self) -> None:
        result = registry.invoke('list_customer_machines', {'customer_id': 'demo'})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['data']['machines']), 1)

    def test_unknown_tool(self) -> None:
        result = registry.invoke('nope', {})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'UNKNOWN_TOOL')

    def test_get_quote_history_ok(self) -> None:
        result = registry.invoke(
            'get_quote_history',
            {'customer_id': 'demo', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['data']['stub'])
        self.assertTrue(len(result['data']['revisions']) > 0)

    def test_get_quote_history_forbidden_cross_tenant(self) -> None:
        result = registry.invoke(
            'get_quote_history',
            {'customer_id': 'other', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'FORBIDDEN')

    def test_get_order_status_ok(self) -> None:
        result = registry.invoke(
            'get_order_status',
            {'customer_id': 'demo', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(len(result['data']['orders']) > 0)

    def test_get_contract_info_ok(self) -> None:
        result = registry.invoke(
            'get_contract_info',
            {'customer_id': 'demo', 'machine_serial': 'A3279'},
        )
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(len(result['data']['contracts']) > 0)

    @override_settings(MCP_HTTP_INVOKE_ENABLED=True)
    def test_http_list_and_invoke(self) -> None:
        client = Client()
        listed = client.get('/api/mcp/tools/')
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(listed.json()['tools'])

        invoked = client.post(
            '/api/mcp/tools/echo/invoke/',
            data='{"message": "http"}',
            content_type='application/json',
        )
        self.assertEqual(invoked.status_code, 200)
        self.assertEqual(invoked.json()['data']['echo'], 'http')

    @override_settings(QDRANT_URL=':memory:')
    def test_markdown_ingestion_and_payload_consistency(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text
        from apps.mcp_server.rag_engine import search as rag_search

        _use_in_memory_qdrant(self)

        sample_md = """<!-- Page 10 -->

# CHAPTER 5: MAINTENANCE

## Section 5.2 - Capping Head Pressure

To adjust capping head pressure on CLOSYS EAGLE VP, turn calibration screw T-804 clockwise.
"""
        meta = IngestMetadata(
            machine_model='CLOSYS EAGLE VP',
            doc_id='test-doc-01',
            doc_type='maintenance_guide',
            source='test_manual.md',
        )
        count = ingest_markdown_text(markdown_text=sample_md, metadata=meta)
        self.assertGreater(count, 0)

        hits = rag_search.search_manuals(
            query='calibration screw T-804 pressure',
            machine_model='CLOSYS EAGLE VP',
            top_k=2,
        )
        self.assertGreaterEqual(len(hits), 1)

        first = hits[0]
        self.assertEqual(first['page_number'], 10)
        self.assertIn('CLOSYS EAGLE VP', first['title'])

    @override_settings(QDRANT_URL=':memory:')
    def test_search_manual_with_markdown_payloads(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

        _use_in_memory_qdrant(self)

        sample_md = """<!-- Page 14 -->

# CHAPTER 3: OPERATING MODES

## Section 3.1 - Operator Safety

Always press emergency stop button before clearing bottle jam on CLOSYS EAGLE VP.
"""
        ingest_markdown_text(
            markdown_text=sample_md,
            metadata=IngestMetadata(
                machine_model='CLOSYS EAGLE VP',
                doc_id='safety-doc',
                doc_type='user_manual',
            ),
        )

        result = registry.invoke(
            'search_manual',
            {
                'customer_id': 'demo',
                'machine_serial': 'A3279',
                'query': 'emergency stop button bottle jam',
                'top_k': 3,
            },
        )
        self.assertEqual(result['status'], 'ok')
        hits = result['data']['hits']
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]['page_number'], 14)

    @override_settings(QDRANT_URL=':memory:')
    def test_general_catalogue_reachable_across_all_models(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text
        from apps.mcp_server.rag_engine import search as rag_search

        _use_in_memory_qdrant(self)

        catalogue_md = """# AROL GENERAL CATALOGUE

## GLOBAL SOLUTIONS

AROL designs capping machines worldwide for food and beverage packaging lines.
"""
        ingest_markdown_text(
            markdown_text=catalogue_md,
            metadata=IngestMetadata(
                machine_model='AROL_GENERAL',
                doc_id='catalogue-doc',
                doc_type='general_catalogue',
            ),
        )

        hits = rag_search.search_manuals(
            query='capping machines worldwide food beverage',
            machine_model='CLOSYS EAGLE VP',
            top_k=2,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(
            any('AROL_GENERAL' in h['title'] or h['doc_type'] == 'general_catalogue' for h in hits)
        )


class ToolStatusTests(TestCase):
    """ToolSpec.status is derived from whether the tool's Output model
    declares a `stub` field (see ToolSpec.status), not hand-set -- so there
    is nothing left to drift between the registry's status and what a
    tool's own response payload claims about itself. These tests are the
    audit: each entry documents *why* a given tool is ready or still a
    stub, and catches a future tool silently landing on the wrong side
    (e.g. someone wires get_order_status to a real ERP but forgets to drop
    `stub: bool = True` from OrderStatusOutput -- this would still fail
    here, now as a status regression rather than a silent lie)."""

    def test_ready_tools_have_a_real_backend(self) -> None:
        ready = {
            'echo': 'trivial passthrough, nothing to stub',
            'get_machine_info': 'real Django ORM query',
            'list_customer_machines': 'real Django ORM query',
            'search_manual': 'real Qdrant/fastembed RAG search',
            'search_error_codes': 'real Qdrant/fastembed RAG search',
        }
        for name, why in ready.items():
            with self.subTest(tool=name):
                spec = registry.get_tool(name)
                assert spec is not None
                self.assertEqual(spec.status, 'ready', f'{name}: expected ready ({why})')

    def test_stub_tools_are_not_yet_backed_by_a_real_system(self) -> None:
        still_stub = {
            'query_telemetry': 'hardcoded value=0.0, no ingestion pipeline',
            'list_spare_parts': 'hardcoded STUB-PART-001, no catalog connected',
            'create_ticket': 'generates a fake ticket_id, no persistence',
            'get_quote_history': 'sample CSV data, no quoting system connected',
            'get_order_status': 'sample CSV data, no ERP connected',
            'get_contract_info': 'sample CSV data, no contracts system connected',
        }
        for name, why in still_stub.items():
            with self.subTest(tool=name):
                spec = registry.get_tool(name)
                assert spec is not None
                self.assertEqual(spec.status, 'stub', f'{name}: expected stub ({why})')

    def test_every_registered_tool_is_accounted_for(self) -> None:
        """Guards the audit itself against silently going stale: if a new
        tool is registered without being added to one of the two lists
        above, this fails loudly instead of the tool going unaudited."""
        audited = {
            'echo', 'get_machine_info', 'list_customer_machines', 'search_manual',
            'search_error_codes', 'query_telemetry', 'list_spare_parts', 'create_ticket',
            'get_quote_history', 'get_order_status', 'get_contract_info',
        }
        registered = {meta['name'] for meta in registry.list_tools()}
        self.assertEqual(
            registered,
            audited,
            'A tool was added/removed without updating the ready/stub audit above.',
        )

