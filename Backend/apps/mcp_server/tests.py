"""Tests for MCP registry + scoped machine tools."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.core.models import Company
from apps.machines.models import Machine, MachineModel
from apps.mcp_server import registry


def _seed_test_fleet(*, demo_username: str = 'demo', other_username: str = 'other'):
    User = get_user_model()
    company = Company.objects.create(
        company_id='CMP-TEST',
        company_name='Test Company',
        country='Italy',
        sector='Beverage',
        city='Novara',
        currency='EUR',
        locale='it-IT',
    )
    other_company = Company.objects.create(
        company_id='CMP-OTHER',
        company_name='Other Company',
        country='France',
        sector='Spirits',
        city='Saintes',
        currency='EUR',
        locale='fr-FR',
    )
    user = User.objects.create_user(
        username=demo_username,
        password='demo',
        user_id='USR-DEMO',
        company=company,
    )
    other = User.objects.create_user(
        username=other_username,
        password='other',
        user_id='USR-OTHER',
        company=other_company,
    )
    machine_model = MachineModel.objects.create(
        model_id='MDL-TEST',
        model_code='CLOSYS EAGLE VP',
        description='Test machine',
        nominal_heads=1,
        container_type='PET bottles',
        cap_type='Plastic screw cap',
        industry_segment='Beverage',
    )
    machine = Machine.objects.create(
        machine_id='MCH-TEST1',
        company=company,
        model=machine_model,
        serial_number='A3279',
        delivery_date=date(2014, 1, 1),
        plant_location='Test Plant',
        configuration_profile='Test config',
        plc_family='SIEMENS-SIMATIC-S7',
    )
    machine2 = Machine.objects.create(
        machine_id='MCH-TEST2',
        company=company,
        model=machine_model,
        serial_number='17478',
        delivery_date=date(2019, 7, 22),
        plant_location='Test Plant 2',
        configuration_profile='Test config 2',
        plc_family='SIEMENS-SIMATIC-S7',
    )
    return user, other, machine, machine2

    def test_markdown_ingestion_and_payload_consistency(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text
        from apps.mcp_server.rag_engine import search as rag_search

        sample_md = """<!-- Page 10 -->

# CHAPTER 5: MAINTENANCE

## Section 5.2 - Capping Head Pressure

To adjust capping head pressure on CLOSYS EAGLE VP, turn calibration screw T-804 clockwise.
"""
        meta = IngestMetadata(
            machine_serial='CLOSYS EAGLE VP',
            doc_id='test-doc-01',
            doc_type='maintenance_guide',
            source='test_manual.md',
        )
        count = ingest_markdown_text(markdown_text=sample_md, metadata=meta)
        self.assertGreater(count, 0)

        hits = rag_search.search_manuals(
            query='calibration screw T-804 pressure',
            machine_serial='CLOSYS EAGLE VP',
            top_k=2,
        )
        self.assertGreaterEqual(len(hits), 1)

        first = hits[0]
        self.assertEqual(first['page_number'], 10)
        self.assertIn('CLOSYS EAGLE VP', first['title'])

    def test_search_manual_with_markdown_payloads(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text

        sample_md = """<!-- Page 14 -->

# CHAPTER 3: OPERATING MODES

## Section 3.1 - Operator Safety

Always press emergency stop button before clearing bottle jam on CLOSYS EAGLE VP.
"""
        ingest_markdown_text(
            markdown_text=sample_md,
            metadata=IngestMetadata(
                machine_serial='A3279',
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

    def test_general_catalogue_reachable_across_all_models(self) -> None:
        from apps.mcp_server.rag_engine.ingest import IngestMetadata, ingest_markdown_text
        from apps.mcp_server.rag_engine import search as rag_search

        catalogue_md = """# AROL GENERAL CATALOGUE

## GLOBAL SOLUTIONS

AROL designs capping machines worldwide for food and beverage packaging lines.
"""
        ingest_markdown_text(
            markdown_text=catalogue_md,
            metadata=IngestMetadata(
                machine_serial='AROL_GENERAL',
                doc_id='catalogue-doc',
                doc_type='general_catalogue',
            ),
        )

        hits = rag_search.search_manuals(
            query='capping machines worldwide food beverage',
            machine_serial='A3279',
            top_k=2,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(
            any('AROL_GENERAL' in h['title'] or h['doc_type'] == 'general_catalogue' for h in hits)
        )

class McpRegistryTests(TestCase):
    def setUp(self) -> None:
        self.user, self.other, self.machine, self.machine2 = _seed_test_fleet()
