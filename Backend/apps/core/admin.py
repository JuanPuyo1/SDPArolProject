from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('company_id', 'company_name', 'country', 'sector', 'city', 'currency')
    search_fields = ('company_id', 'company_name', 'city', 'country')
    list_filter = ('country', 'sector', 'currency')
