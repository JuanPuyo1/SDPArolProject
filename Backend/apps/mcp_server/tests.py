"""Tests for MCP registry + scoped machine tools."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.core.models import Company
from apps.machines.models import Machine, MachineModel
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


def _seed_test_fleet(*, demo_username: str = "demo", other_username: str = "other"):
    User = get_user_model()
    company = Company.objects.create(
        company_id="CMP-TEST",
        company_name="Test Company",
        country="Italy",
        sector="Beverage",
        city="Novara",
        currency="EUR",
        locale="it-IT",
    )
    other_company = Company.objects.create(
        company_id="CMP-OTHER",
        company_name="Other Company",
        country="France",
        sector="Spirits",
        city="Saintes",
        currency="EUR",
        locale="fr-FR",
    )
    user = User.objects.create_user(
        username=demo_username,
        password="demo",
        user_id="USR-DEMO",
        company=company,
    )
    other = User.objects.create_user(
        username=other_username,
        password="other",
        user_id="USR-OTHER",
        company=other_company,
    )
    machine_model = MachineModel.objects.create(
        model_id="MDL-TEST",
        model_code="CLOSYS EAGLE VP",
        description="Test machine",
        nominal_heads=1,
        container_type="PET bottles",
        cap_type="Plastic screw cap",
        industry_segment="Beverage",
    )
    machine = Machine.objects.create(
        machine_id="MCH-TEST1",
        company=company,
        model=machine_model,
        serial_number="A3279",
        delivery_date=date(2014, 1, 1),
        plant_location="Test Plant",
        configuration_profile="Test config",
        plc_family="SIEMENS-SIMATIC-S7",
    )
    machine2 = Machine.objects.create(
        machine_id="MCH-TEST2",
        company=company,
        model=machine_model,
        serial_number="17478",
        delivery_date=date(2019, 7, 22),
        plant_location="Test Plant 2",
        configuration_profile="Test config 2",
        plc_family="SIEMENS-SIMATIC-S7",
    )
    return user, other, machine, machine2


class McpRegistryTests(TestCase):
    def setUp(self) -> None:
        self.user, self.other, self.machine, self.machine2 = _seed_test_fleet()
