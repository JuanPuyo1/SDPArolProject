"""Tests for chat SSE endpoint and stub orchestrator."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.agents.stub_orchestrator import StubOrchestrator
from apps.agents.troubleshooting_service_agent import AgentIntent, classify_intent
from apps.machines.models import Machine


class StubOrchestratorTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        Machine.objects.create(
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

    @override_settings(ANTHROPIC_API_KEY='')
    def test_stub_calls_mcp_tools_and_streams_canned_tokens(self) -> None:
        orchestrator = StubOrchestrator()
        chunks = list(
            orchestrator.run(
                customer_id='demo',
                machine_serial='A3279',
                message='Alarm E042 star-wheel jam',
            ),
        )

        types = [c.type for c in chunks]
        self.assertIn('tool', types)
        self.assertIn('token', types)
        self.assertEqual(types[-1], 'done')

        types = [c.type for c in chunks]
        self.assertIn('step', types)

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('get_machine_info', tool_names)
        self.assertIn('search_error_codes', tool_names)
        self.assertIn('search_manual', tool_names)

        text = ''.join(c.content for c in chunks if c.type == 'token')
        self.assertIn('A3279', text)
        self.assertIn('troubleshooting_service', text)

    @override_settings(ANTHROPIC_API_KEY='')
    def test_service_intent_opens_ticket(self) -> None:
        orchestrator = StubOrchestrator()
        chunks = list(
            orchestrator.run(
                customer_id='demo',
                machine_serial='A3279',
                message='Please send a technician — machine keeps stopping',
            ),
        )

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('create_ticket', tool_names)

        text = ''.join(c.content for c in chunks if c.type == 'token')
        self.assertIn('TKT-', text)

    @override_settings(ANTHROPIC_API_KEY='')
    def test_manual_queries_trigger_search_manual_tool(self) -> None:
        orchestrator = StubOrchestrator()
        chunks = list(
            orchestrator.run(
                customer_id='demo',
                machine_serial='A3279',
                message='How do I adjust torque on the capping head?',
            ),
        )

        tool_names = [c.tool for c in chunks if c.type == 'tool']
        self.assertIn('search_manual', tool_names)


class TroubleshootingServiceAgentTests(TestCase):
    def test_classify_intent(self) -> None:
        self.assertEqual(
            classify_intent('Alarm E042 star-wheel jam'),
            AgentIntent.TROUBLESHOOTING,
        )
        self.assertEqual(
            classify_intent('Send a technician for field service'),
            AgentIntent.SERVICE,
        )
        self.assertEqual(classify_intent('What machine is this?'), AgentIntent.GENERAL)


class ChatViewTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(username='demo', password='demo')
        Machine.objects.create(
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
        self.client = Client()

    def test_chat_requires_auth(self) -> None:
        response = self.client.post(
            '/api/agents/chat/',
            data={'message': 'hello'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(ANTHROPIC_API_KEY='')
    def test_chat_streams_sse_for_authenticated_user(self) -> None:
        self.client.login(username='demo', password='demo')
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
