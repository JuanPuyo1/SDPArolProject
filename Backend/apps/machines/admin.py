from django.contrib import admin

from .models import (
    Alarm,
    Machine,
    MachineModel,
    MachineUnit,
    MaintenanceTicket,
    TelemetrySnapshot,
)


class MachineUnitInline(admin.TabularInline):
    model = MachineUnit
    extra = 0
    ordering = ('sort_order', 'code')


@admin.register(MachineModel)
class MachineModelAdmin(admin.ModelAdmin):
    list_display = (
        'model_id',
        'model_code',
        'nominal_heads',
        'primitive_diameter',
        'industry_segment',
    )
    search_fields = ('model_id', 'model_code', 'description')


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number',
        'machine_id',
        'company',
        'model',
        'delivery_date',
        'plant_location',
        'plc_family',
    )
    list_filter = ('plc_family', 'delivery_date')
    search_fields = ('serial_number', 'machine_id', 'plant_location', 'configuration_profile')
    raw_id_fields = ('company', 'model')
    inlines = [MachineUnitInline]


@admin.register(TelemetrySnapshot)
class TelemetrySnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'telemetry_id',
        'machine',
        'timestamp',
        'operational_status',
        'production_rate_bph',
        'alarm_count',
    )
    list_filter = ('operational_status',)
    raw_id_fields = ('machine',)
    date_hierarchy = 'timestamp'


@admin.register(Alarm)
class AlarmAdmin(admin.ModelAdmin):
    list_display = ('alarm_id', 'machine', 'timestamp', 'alarm_code', 'severity', 'alarm_status')
    list_filter = ('severity', 'alarm_status')
    search_fields = ('alarm_id', 'alarm_code')
    raw_id_fields = ('machine',)


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_id',
        'machine',
        'ticket_type',
        'ticket_status',
        'priority',
        'created_date',
        'owner_role',
    )
    list_filter = ('ticket_type', 'ticket_status', 'priority')
    raw_id_fields = ('machine', 'alarm')
