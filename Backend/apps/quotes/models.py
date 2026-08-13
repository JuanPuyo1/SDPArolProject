from django.db import models


class Quote(models.Model):
    """Commercial quote header for a customer company."""

    quote_id = models.CharField(max_length=32, primary_key=True)
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='quotes',
    )
    currency = models.CharField(max_length=3)
    created_at = models.DateField()
    valid_until = models.DateField()
    description = models.TextField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.quote_id


class QuoteRevision(models.Model):
    """Revision of a quote with status, discount, and change summary."""

    quote_revision_id = models.CharField(max_length=32, primary_key=True)
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='revisions',
    )
    revision_number = models.PositiveSmallIntegerField()
    revision_status = models.CharField(max_length=32)
    issued_at = models.DateField()
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4)
    change_summary = models.TextField()

    class Meta:
        ordering = ['quote', 'revision_number']
        unique_together = [('quote', 'revision_number')]

    def __str__(self) -> str:
        return f'{self.quote.quote_id} rev {self.revision_number}'


class QuoteLine(models.Model):
    """Line item on a quote revision, optionally tied to a machine."""

    quote_line_id = models.CharField(max_length=32, primary_key=True)
    quote_revision = models.ForeignKey(
        QuoteRevision,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    machine = models.ForeignKey(
        'machines.Machine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_lines',
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()

    class Meta:
        ordering = ['quote_line_id']

    def __str__(self) -> str:
        return self.quote_line_id


class Order(models.Model):
    """Confirmed order converted from an accepted quote revision."""

    order_id = models.CharField(max_length=32, primary_key=True)
    quote = models.ForeignKey(
        Quote,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='orders',
    )
    order_status = models.CharField(max_length=32)
    order_date = models.DateField()
    expected_delivery_date = models.DateField()
    shipment_status = models.CharField(max_length=32)
    currency = models.CharField(max_length=3)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-order_date']

    def __str__(self) -> str:
        return self.order_id


class OrderLine(models.Model):
    """Fulfillment line on a confirmed order."""

    order_line_id = models.CharField(max_length=32, primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    fulfillment_status = models.CharField(max_length=32)

    class Meta:
        ordering = ['order_line_id']

    def __str__(self) -> str:
        return self.order_line_id
