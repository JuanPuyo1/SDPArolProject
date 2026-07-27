from django.contrib import admin

from .models import Machine, MachineUnit


class MachineUnitInline(admin.TabularInline):
    model = MachineUnit
    extra = 0
    ordering = ('sort_order', 'code')


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number',
        'model',
        'owner',
        'manufacturing_year',
        'manufacturer',
    )
    list_filter = ('manufacturing_year', 'manufacturer')
    search_fields = ('serial_number', 'model', 'full_model', 'qr_token')
    inlines = [MachineUnitInline]
    raw_id_fields = ('owner',)
