from django.db import models


class Company(models.Model):
    """Customer organization (tenant) owning machines, quotes, and orders."""

    company_id = models.CharField(max_length=32, primary_key=True)
    company_name = models.CharField(max_length=256)
    country = models.CharField(max_length=128)
    sector = models.CharField(max_length=128)
    city = models.CharField(max_length=128)
    currency = models.CharField(max_length=3)
    locale = models.CharField(max_length=16)

    class Meta:
        verbose_name_plural = 'companies'
        ordering = ['company_name']

    def __str__(self) -> str:
        return self.company_name
