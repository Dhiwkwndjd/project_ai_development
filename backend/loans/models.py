"""Брони (выдачи) книг и история их статусов."""

from django.conf import settings
from django.db import models

from catalog.models import BookCopy
from loans.statuses import LoanStatus


class Loan(models.Model):
    """Бронь или выдача экземпляра книги читателю."""

    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="loans",
        verbose_name="Читатель",
    )
    copy = models.ForeignKey(
        BookCopy, on_delete=models.PROTECT, related_name="loans", verbose_name="Экземпляр"
    )
    start_date = models.DateField("Дата начала")
    due_date = models.DateField("Дата возврата")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=LoanStatus.choices,
        default=LoanStatus.CREATED,
    )
    comment = models.CharField("Комментарий", max_length=255, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        db_table = "loans"
        verbose_name = "Бронь"
        verbose_name_plural = "Брони"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["copy", "start_date", "due_date"], name="loans_copy_dates_idx"
            ),
            models.Index(fields=["reader"], name="loans_reader_idx"),
            models.Index(fields=["status"], name="loans_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(due_date__gt=models.F("start_date")),
                name="loan_due_after_start",
            ),
        ]

    def __str__(self):
        return f"Бронь #{self.pk}: {self.copy} для {self.reader}"


class LoanStatusHistory(models.Model):
    """История изменения статуса брони."""

    loan = models.ForeignKey(
        Loan, on_delete=models.CASCADE, related_name="status_history", verbose_name="Бронь"
    )
    old_status = models.CharField(
        "Было", max_length=20, choices=LoanStatus.choices, blank=True
    )
    new_status = models.CharField("Стало", max_length=20, choices=LoanStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_status_changes",
        verbose_name="Кто изменил",
    )
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        db_table = "loan_status_history"
        verbose_name = "История статуса брони"
        verbose_name_plural = "История статусов броней"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["loan", "created_at"], name="history_loan_time_idx"),
        ]

    def __str__(self):
        return f"#{self.loan_id}: {self.old_status or '—'} → {self.new_status}"
