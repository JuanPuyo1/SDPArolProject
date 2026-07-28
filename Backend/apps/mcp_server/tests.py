"""Tests for MCP registry + scoped machine tools."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.machines.models import Machine
from apps.mcp_server import registry


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
