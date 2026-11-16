"""Админка очереди."""

from django.contrib import admin

from reservations.models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "reader", "status", "hold_copy", "hold_until")
    list_filter = ("status",)
    search_fields = ("book__title", "reader__email")
