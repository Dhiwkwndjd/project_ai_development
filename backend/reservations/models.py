"""Очередь читателей на книгу и удержания экземпляров."""

from django.conf import settings
from django.db import models

from catalog.models import Book, BookCopy


class Reservation(models.Model):
    """Заявка читателя в очереди на книгу.

    waiting   — ждёт свободный экземпляр;
    ready     — экземпляр удержан за читателем до hold_until;
    fulfilled — читатель оформил бронь;
    cancelled — заявка отменена;
    expired   — срок удержания истёк.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидает"
        READY = "ready", "Готова к выдаче"
        FULFILLED = "fulfilled", "Выполнена"
        CANCELLED = "cancelled", "Отменена"
        EXPIRED = "expired", "Просрочена"

    ACTIVE_STATUSES = (Status.WAITING, Status.READY)

    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="reservations", verbose_name="Книга"
    )
    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name="Читатель",
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.WAITING
    )
    hold_copy = models.ForeignKey(
        BookCopy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="holds",
        verbose_name="Удержанный экземпляр",
    )
    hold_until = models.DateTimeField("Удержание до", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        db_table = "reservations"
        verbose_name = "Заявка в очереди"
        verbose_name_plural = "Очередь заявок"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["book", "status", "created_at"], name="reserv_book_status_idx"
            ),
            models.Index(fields=["reader", "status"], name="reserv_reader_idx"),
        ]

    def __str__(self):
        return f"Заявка #{self.pk}: {self.book} для {self.reader} ({self.status})"
