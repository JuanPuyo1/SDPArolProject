from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.core.models import Company
from apps.machines.models import Machine, MachineModel


class MachineDetailLookupTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.company = Company.objects.create(
            company_id="CMP-LOOKUP",
            company_name="Lookup Co",
            country="Italy",
            sector="Beverage",
            city="Novara",
            currency="EUR",
            locale="it-IT",
        )
        other_company = Company.objects.create(
            company_id="CMP-LOOKUP-OTHER",
            company_name="Other Co",
            country="France",
            sector="Spirits",
            city="Saintes",
            currency="EUR",
            locale="fr-FR",
        )
        self.user = User.objects.create_user(
            username="demo",
            password="demo",
            company=self.company,
            visibility="full",
        )
        model = MachineModel.objects.create(
            model_id="MDL-LOOKUP",
            model_code="CLOSYS EAGLE VP",
            description="Test machine",
            nominal_heads=1,
            container_type="PET bottles",
            cap_type="Plastic screw cap",
            industry_segment="Beverage",
        )
        self.machine = Machine.objects.create(
            machine_id="MCH-0004",
            company=self.company,
            model=model,
            serial_number="17478",
            delivery_date=date(2019, 7, 22),
            plant_location="Line 1",
            configuration_profile="Test config",
            plc_family="SIEMENS-SIMATIC-S7",
        )
        Machine.objects.create(
            machine_id="MCH-FOREIGN",
            company=other_company,
            model=model,
            serial_number="99999",
            delivery_date=date(2018, 1, 1),
            plant_location="Other plant",
            configuration_profile="Foreign",
            plc_family="SIEMENS-SIMATIC-S7",
        )
        self.client = Client()
        self.client.login(username="demo", password="demo")

    def test_lookup_by_serial_number(self) -> None:
        response = self.client.get("/api/machines/17478/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["machine"]["machineId"], "MCH-0004")

    def test_lookup_by_machine_id(self) -> None:
        response = self.client.get("/api/machines/MCH-0004/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["machine"]["serialNumber"], "17478")

    def test_foreign_machine_is_forbidden(self) -> None:
        response = self.client.get("/api/machines/MCH-FOREIGN/")
        self.assertEqual(response.status_code, 403)

    def test_unknown_machine_is_not_found(self) -> None:
        response = self.client.get("/api/machines/does-not-exist/")
        self.assertEqual(response.status_code, 404)
