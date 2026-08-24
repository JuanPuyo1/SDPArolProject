"""Commercial data conventions from README_AROL.md."""

from decimal import Decimal

from django.test import Client, TestCase

from apps.core.test_fixtures import PASSWORD, seed_spec_fleet
from apps.mcp_server import orders_data
from apps.quotes.models import OrderLine, QuoteLine, QuoteRevision
from apps.quotes.serializers import order_to_dict


class OrderHttpTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()
        self.client = Client()

    def test_orders_are_tenant_scoped(self) -> None:
        self.client.login(username="acme_comm", password=PASSWORD)
        response = self.client.get("/api/quotes/orders/")
        self.assertEqual(response.status_code, 200)
        ids = {row["orderId"] for row in response.json()["orders"]}
        self.assertIn("ORD-SPEC-1", ids)
        self.assertTrue(all(row["companyId"] == "CMP-ACME" for row in response.json()["orders"]))

    def test_other_company_does_not_see_acme_orders(self) -> None:
        self.client.login(username="other_full", password=PASSWORD)
        response = self.client.get("/api/quotes/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["orders"], [])

    def test_order_lines_carry_fulfillment_only(self) -> None:
        """OrderLines track fulfilment only: no item, quantity, or price."""
        line = OrderLine.objects.get(order_line_id="OL-1")
        self.assertFalse(hasattr(line, "price"))
        self.assertFalse(hasattr(line, "quantity"))
        payload = order_to_dict(self.fleet.order)
        self.assertEqual(payload["lines"][0]["fulfillmentStatus"], "Delivered")
        self.assertNotIn("price", payload["lines"][0])
        self.assertNotIn("quantity", payload["lines"][0])


class QuoteConventionTests(TestCase):
    def setUp(self) -> None:
        self.fleet = seed_spec_fleet()

    def test_quote_lines_belong_to_revision_not_quote(self) -> None:
        line = QuoteLine.objects.get(quote_line_id="QL-2A")
        self.assertEqual(line.quote_revision_id, "QREV-2")
        self.assertFalse(hasattr(line, "quote_id"))

    def test_quote_line_without_machine_is_kept(self) -> None:
        line = QuoteLine.objects.get(quote_line_id="QL-2B")
        self.assertIsNone(line.machine_id)

    def test_highest_revision_number_is_current(self) -> None:
        numbers = list(
            QuoteRevision.objects.filter(quote=self.fleet.quote)
            .order_by("revision_number")
            .values_list("revision_number", "revision_status")
        )
        self.assertEqual(numbers[-1], (2, "Approved"))

    def test_quote_history_does_not_reapply_discount(self) -> None:
        """QuoteLines.price is already net of discountRate."""
        rows = orders_data.quote_history(self.fleet.acme, quote_id="QUO-SPEC-1")
        rev2 = next(r for r in rows if r["revision_number"] == 2)
        self.assertEqual(rev2["amount_eur"], 9000.0)
        self.assertEqual(self.fleet.approved_revision.discount_rate, Decimal("0.1500"))

    def test_orphan_quote_never_became_an_order(self) -> None:
        self.assertFalse(self.fleet.orphan_quote.orders.exists())

    def test_rejected_final_revision_is_present(self) -> None:
        last = (
            QuoteRevision.objects.filter(quote=self.fleet.rejected_quote)
            .order_by("revision_number")
            .last()
        )
        self.assertEqual(last.revision_status, "Rejected")

    def test_order_amount_comes_from_approved_revision_not_later_rejected(self) -> None:
        """Spec: order content comes from the approved revision's quote lines.

        A later Rejected revision must not replace the Approved amount.
        """
        rows = orders_data.order_status(self.fleet.acme)
        rejected_src = next(r for r in rows if r["order_id"] == "ORD-REJECT-SRC")
        self.assertEqual(rejected_src["amount_eur"], 1000.0)
        self.assertIn("Approved revision", rejected_src["item_summary"])
