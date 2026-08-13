from django.db import models


class MachineModel(models.Model):
    """Catalog entry describing an AROL machine product line."""

    model_id = models.CharField(max_length=32, primary_key=True)
    model_code = models.CharField(max_length=128)
    description = models.TextField()
    primitive_diameter = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        null=True,
        blank=True,
    )
    nominal_heads = models.PositiveSmallIntegerField()
    container_type = models.CharField(max_length=256)
    cap_type = models.CharField(max_length=256)
    industry_segment = models.CharField(max_length=128)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['model_code']

    def __str__(self) -> str:
        return self.model_code


class Machine(models.Model):
    """Installed machine instance owned by a customer company."""

    machine_id = models.CharField(max_length=32, primary_key=True)
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='machines',
    )
    model = models.ForeignKey(
        MachineModel,
        on_delete=models.PROTECT,
        related_name='machines',
    )
    serial_number = models.CharField(max_length=64, unique=True, db_index=True)
    delivery_date = models.DateField()
    plant_location = models.CharField(max_length=256)
    configuration_profile = models.TextField()
    plc_family = models.CharField(max_length=128)
    software_version = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['serial_number']

    def __str__(self) -> str:
        return f'{self.model.model_code} ({self.serial_number})'


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


class TelemetrySnapshot(models.Model):
    """Hourly operational telemetry reading for a machine."""

    telemetry_id = models.CharField(max_length=32, primary_key=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='telemetry_snapshots',
    )
    timestamp = models.DateTimeField(db_index=True)
    operational_status = models.CharField(max_length=32)
    production_rate_bph = models.PositiveIntegerField()
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=1)
    alarm_count = models.PositiveSmallIntegerField()
    temperature_c = models.DecimalField(max_digits=5, decimal_places=1)
    energy_kwh = models.DecimalField(max_digits=8, decimal_places=2)
    health_note = models.TextField()

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['machine', 'timestamp']),
        ]

    def __str__(self) -> str:
        return f'{self.telemetry_id} @ {self.timestamp:%Y-%m-%d %H:%M}'


class Alarm(models.Model):
    """Machine alarm event raised during production."""

    alarm_id = models.CharField(max_length=32, primary_key=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='alarms',
    )
    timestamp = models.DateTimeField(db_index=True)
    alarm_code = models.CharField(max_length=128)
    severity = models.CharField(max_length=16)
    alarm_status = models.CharField(max_length=32)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self) -> str:
        return f'{self.alarm_code} ({self.alarm_id})'


class MaintenanceTicket(models.Model):
    """Service or maintenance ticket linked to a machine (optionally to an alarm)."""

    ticket_id = models.CharField(max_length=32, primary_key=True)
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name='maintenance_tickets',
    )
    alarm = models.ForeignKey(
        Alarm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_tickets',
    )
    ticket_type = models.CharField(max_length=64)
    ticket_status = models.CharField(max_length=32)
    priority = models.CharField(max_length=16)
    created_date = models.DateField()
    owner_role = models.CharField(max_length=64)

    class Meta:
        ordering = ['-created_date']

    def __str__(self) -> str:
        return f'{self.ticket_id} — {self.ticket_type}'
