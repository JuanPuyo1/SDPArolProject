from django.conf import settings
from django.db import models


class Machine(models.Model):
    """
    Customer-owned capping machine record.

    One user/customer owns many machines. Fields mirror the frontend
    machine detail view (identification, technical, operating, units).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='machines',
        help_text='Customer/user that owns this machine (tenant scope).',
    )
    serial_number = models.CharField(max_length=64, unique=True, db_index=True)
    qr_token = models.CharField(
        max_length=128,
        blank=True,
        default='',
        help_text='Token encoded in on-machine QR codes for lookup.',
    )

    model = models.CharField(max_length=128)
    full_model = models.CharField(max_length=256)
    manufacturing_year = models.PositiveIntegerField()
    manufacturer = models.CharField(max_length=128, default='AROL S.p.A.')
    site = models.CharField(max_length=256, blank=True, default='')

    description = models.TextField()

    # Identification
    machine_type = models.CharField(max_length=256)
    pitch_diameter = models.CharField(max_length=64)
    heads = models.PositiveSmallIntegerField(default=1)
    rotation = models.CharField(max_length=64)

    # Manual
    manual_revision = models.CharField(max_length=32, blank=True, default='')
    manual_date = models.CharField(max_length=32, blank=True, default='')
    manual_url = models.CharField(max_length=512, blank=True, default='')

    # Weight & capacity
    weight_value = models.CharField(max_length=32)
    weight_unit = models.CharField(max_length=16, default='kg')
    productive_capacity_value = models.CharField(max_length=32)
    productive_capacity_unit = models.CharField(max_length=32, default='pcs/h')

    # Electrical
    electrical_main_supply = models.CharField(max_length=128)
    electrical_auxiliary_supply = models.CharField(max_length=128)
    electrical_total_installed_power = models.CharField(max_length=64)
    electrical_breakdown = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"label": "...", "value": "..."} power breakdown rows.',
    )

    # Pneumatic
    pneumatic_sterile_air_capacity = models.CharField(max_length=64)
    pneumatic_min_pressure = models.CharField(max_length=32)
    pneumatic_max_pressure = models.CharField(max_length=32)

    # Operating conditions
    operating_temperature = models.CharField(max_length=128)
    operating_environment = models.TextField()
    operating_noise = models.TextField()

    certifications = models.JSONField(
        default=list,
        blank=True,
        help_text='List of certification strings, e.g. ["CE", "Directive 2006/42/EC"].',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['serial_number']

    def __str__(self) -> str:
        return f'{self.model} ({self.serial_number})'


class MachineUnit(models.Model):
    """Main mechanical/electrical unit of a machine (caps sorter, star-wheel, …)."""

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='main_units',
    )
    code = models.CharField(max_length=8)
    name = models.CharField(max_length=128)
    note = models.TextField(blank=True, default='')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'code']
        unique_together = [('machine', 'code')]

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'
