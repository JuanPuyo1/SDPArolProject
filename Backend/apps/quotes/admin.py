from django.contrib import admin

from .models import Order, OrderLine, Quote, QuoteLine, QuoteRevision


class QuoteRevisionInline(admin.TabularInline):
    model = QuoteRevision
    extra = 0
    show_change_link = True


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('quote_id', 'company', 'currency', 'created_at', 'valid_until')
    search_fields = ('quote_id', 'description')
    raw_id_fields = ('company',)
    inlines = [QuoteRevisionInline]


@admin.register(QuoteRevision)
class QuoteRevisionAdmin(admin.ModelAdmin):
    list_display = (
        'quote_revision_id',
        'quote',
        'revision_number',
        'revision_status',
        'issued_at',
        'discount_rate',
    )
    list_filter = ('revision_status',)
    raw_id_fields = ('quote',)
    inlines = [QuoteLineInline]


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_id',
        'company',
        'quote',
        'order_status',
        'order_date',
        'shipment_status',
    )
    list_filter = ('order_status', 'shipment_status', 'currency')
    search_fields = ('order_id', 'notes')
    raw_id_fields = ('company', 'quote')
    inlines = [OrderLineInline]
