"""Authentication and Access Model tests (README_AROL.md)."""

from django.test import Client, TestCase

from apps.core.test_fixtures import PASSWORD, seed_spec_fleet


class AuthSessionTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()

    def test_login_rejects_invalid_credentials(self) -> None:
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "acme_full", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_login_returns_visibility_and_company(self) -> None:
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "acme_tech", "password": PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user = response.json()["user"]
        self.assertEqual(user["visibility"], "technician")
        self.assertEqual(user["company_id"], "CMP-ACME")
        self.assertEqual(user["user_id"], "USR-ACME-TECH")

    def test_profile_requires_authentication(self) -> None:
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

    def test_profile_returns_own_user_row(self) -> None:
        self.client.login(username="acme_full", password=PASSWORD)
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 200)
        user = response.json()["user"]
        self.assertEqual(user["username"], "acme_full")
        self.assertEqual(user["visibility"], "full")

    def test_logout_ends_session(self) -> None:
        self.client.login(username="acme_full", password=PASSWORD)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)


class VisibilityHelperTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()

    def test_technician_cannot_list_orders(self) -> None:
        self.client.login(username="acme_tech", password=PASSWORD)
        response = self.client.get("/api/quotes/orders/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot view", response.json()["error"])

    def test_commercial_cannot_list_maintenance_tickets(self) -> None:
        self.client.login(username="acme_comm", password=PASSWORD)
        response = self.client.get("/api/machines/tickets/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("cannot view", response.json()["error"])

    def test_full_role_can_list_orders_and_tickets(self) -> None:
        self.client.login(username="acme_full", password=PASSWORD)
        self.assertEqual(self.client.get("/api/quotes/orders/").status_code, 200)
        self.assertEqual(self.client.get("/api/machines/tickets/").status_code, 200)

    def test_commercial_can_list_orders(self) -> None:
        self.client.login(username="acme_comm", password=PASSWORD)
        response = self.client.get("/api/quotes/orders/")
        self.assertEqual(response.status_code, 200)
        ids = {row["orderId"] for row in response.json()["orders"]}
        self.assertIn("ORD-SPEC-1", ids)

    def test_technician_can_list_maintenance_tickets(self) -> None:
        self.client.login(username="acme_tech", password=PASSWORD)
        response = self.client.get("/api/machines/tickets/")
        self.assertEqual(response.status_code, 200)
        ids = {row["ticketId"] for row in response.json()["tickets"]}
        self.assertIn("TKT-FROM-ALM", ids)
        self.assertIn("TKT-NO-ALM", ids)
