"""Company tenant model tests."""

from django.test import TestCase

from apps.core.models import Company
from apps.core.test_fixtures import seed_spec_fleet


class CompanyModelTests(TestCase):
    def test_company_fields_match_dataset_schema(self) -> None:
        seed_spec_fleet()
        company = Company.objects.get(company_id="CMP-ACME")
        self.assertEqual(company.company_name, "Acme Bottling")
        self.assertEqual(company.country, "Italy")
        self.assertEqual(company.city, "Novara")
        self.assertEqual(company.sector, "Beverage")
        self.assertEqual(company.currency, "EUR")
        self.assertEqual(company.locale, "it-IT")
