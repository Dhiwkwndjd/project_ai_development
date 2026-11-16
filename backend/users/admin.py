"""Настройка админки для пользователей библиотеки."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import ActivityLog, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("email", "full_name", "phone")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("full_name", "phone")}),
        ("Доступ", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Даты", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "phone", "role", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("created_at",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "description", "ip_address")
    list_filter = ("action",)
    search_fields = ("user__email", "description")
    readonly_fields = (
        "user",
        "action",
        "entity_type",
        "entity_id",
        "description",
        "ip_address",
        "created_at",
    )
