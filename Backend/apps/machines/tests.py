"""Machine fleet, QR lookup, manuals, and operational HTTP tests."""

from django.test import Client, TestCase

from apps.core.test_fixtures import PASSWORD, seed_spec_fleet
from apps.machines.manuals import manual_filename_for_serial, resolve_manual_url
from apps.machines.models import MachineModel, MaintenanceTicket
from apps.machines.serializers import machine_to_dict, maintenance_ticket_to_dict


class MachineDetailLookupTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()
        self.client.login(username="acme_full", password=PASSWORD)

    def test_lookup_by_serial_number(self) -> None:
        response = self.client.get("/api/machines/17478/")
        self.assertEqual(response.status_code, 200)
        machine = response.json()["machine"]
        self.assertEqual(machine["machineId"], "MCH-0004")
        self.assertEqual(machine["serialNumber"], "17478")

    def test_lookup_by_machine_id(self) -> None:
        """QR codes may encode machineId or serialNumber (README_AROL.md)."""
        response = self.client.get("/api/machines/MCH-0004/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["machine"]["serialNumber"], "17478")

    def test_foreign_machine_is_forbidden_not_empty(self) -> None:
        response = self.client.get("/api/machines/MCH-FOREIGN/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("not assigned", response.json()["error"])

    def test_foreign_serial_is_forbidden_not_empty(self) -> None:
        response = self.client.get("/api/machines/99999/")
        self.assertEqual(response.status_code, 403)

    def test_unknown_machine_is_not_found(self) -> None:
        response = self.client.get("/api/machines/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_lookup_is_rejected(self) -> None:
        anon = Client()
        self.assertEqual(anon.get("/api/machines/17478/").status_code, 401)


class MachineListAndIdentityTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()

    def test_every_role_can_list_own_company_machines(self) -> None:
        for username in ("acme_full", "acme_tech", "acme_comm"):
            client = Client()
            client.login(username=username, password=PASSWORD)
            response = client.get("/api/machines/")
            self.assertEqual(response.status_code, 200, username)
            serials = {m["serialNumber"] for m in response.json()["machines"]}
            self.assertEqual(serials, {"17478", "A3279"})
            self.assertNotIn("99999", serials)

    def test_company_with_users_but_no_machines_returns_empty_list(self) -> None:
        self.client.login(username="empty_user", password=PASSWORD)
        response = self.client.get("/api/machines/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["machines"], [])

    def test_default_machine_404_when_company_owns_none(self) -> None:
        self.client.login(username="empty_user", password=PASSWORD)
        response = self.client.get("/api/machines/default/")
        self.assertEqual(response.status_code, 404)

    def test_payload_includes_configuration_profile_and_model(self) -> None:
        self.client.login(username="acme_full", password=PASSWORD)
        machine = self.client.get("/api/machines/17478/").json()["machine"]
        self.assertIn("24000 BPH", machine["configurationProfile"])
        self.assertEqual(machine["model"]["modelCode"], "CLOSYS EAGLE VP")
        self.assertEqual(machine["model"]["primitiveDiameter"], 180.0)
        self.assertEqual(machine["plcFamily"], "SIEMENS-SIMATIC-S7")
        self.assertEqual(machine["company"]["companyId"], "CMP-ACME")

    def test_primitive_diameter_may_be_empty(self) -> None:
        model = MachineModel.objects.get(model_id="MDL-NODIAM")
        self.assertIsNone(model.primitive_diameter)
        self.client.login(username="acme_full", password=PASSWORD)
        machine = self.client.get("/api/machines/A3279/").json()["machine"]
        self.assertIsNone(machine["model"]["primitiveDiameter"])


class ManualConventionTests(TestCase):
    def test_manual_filename_uses_serial_number(self) -> None:
        self.assertEqual(
            manual_filename_for_serial("17478"),
            "17478_manual_EN.pdf",
        )

    def test_missing_pdf_resolves_to_none(self) -> None:
        self.assertIsNone(resolve_manual_url("no-such-serial"))


class MaintenanceTicketHttpTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()
        self.client.login(username="acme_tech", password=PASSWORD)

    def test_tickets_are_scoped_to_own_company(self) -> None:
        response = self.client.get("/api/machines/tickets/")
        self.assertEqual(response.status_code, 200)
        tickets = response.json()["tickets"]
        serials = {t["serialNumber"] for t in tickets}
        self.assertEqual(serials, {"17478"})

    def test_ticket_without_alarm_is_not_dropped(self) -> None:
        """Empty MaintenanceTickets.alarmId must survive (no inner-join drop)."""
        ticket = MaintenanceTicket.objects.get(ticket_id="TKT-NO-ALM")
        self.assertIsNone(ticket.alarm_id)
        payload = maintenance_ticket_to_dict(ticket)
        self.assertIsNone(payload["alarmId"])
        ids = {
            row["ticketId"]
            for row in self.client.get("/api/machines/tickets/").json()["tickets"]
        }
        self.assertIn("TKT-NO-ALM", ids)


class MachineSerializerTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_machine_to_dict_does_not_leak_foreign_company(self) -> None:
        payload = machine_to_dict(self.fleet.machine)
        self.assertEqual(payload["company"]["companyId"], "CMP-ACME")
        self.assertEqual(payload["machineId"], "MCH-0004")
