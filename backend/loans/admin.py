"""Админка броней."""

from django.contrib import admin

from loans.models import Loan, LoanStatusHistory


class LoanStatusHistoryInline(admin.TabularInline):
    model = LoanStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "created_at")
    can_delete = False


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("id", "reader", "copy", "start_date", "due_date", "status")
    list_filter = ("status", "start_date")
    search_fields = ("reader__email", "copy__inventory_number", "copy__book__title")
    inlines = [LoanStatusHistoryInline]


@admin.register(LoanStatusHistory)
class LoanStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("loan", "old_status", "new_status", "changed_by", "created_at")
    list_filter = ("new_status",)
