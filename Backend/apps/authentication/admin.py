from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'user_id',
        'username',
        'email',
        'company',
        'visibility',
        'job_title',
        'is_staff',
    )
    list_filter = ('visibility', 'is_staff', 'company')
    search_fields = ('user_id', 'username', 'email', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        (
            'Company & role',
            {'fields': ('user_id', 'company', 'job_title', 'visibility')},
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'Company & role',
            {'fields': ('user_id', 'company', 'job_title', 'visibility')},
        ),
    )
