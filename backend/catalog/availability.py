"""Расчёт занятости экземпляров на интервал.

Правила совпадают с `loans/services.py`: экземпляр занят, если на даты
пересекается бронь в статусе `created`/`active` или действует чужое
удержание `ready`. Смежные интервалы не конфликтуют.
"""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from catalog.models import BookCopy
from loans.models import Loan
from loans.statuses import BLOCKING_STATUSES
from reservations.models import Reservation
from reservations.services import expire_outdated_holds

DEFAULT_AVAILABILITY_DAYS = 14


def current_period():
    """Интервал «свободно сейчас» для списка и карточки."""
    today = timezone.localdate()
    return today, today + timedelta(days=1)


def busy_copy_ids(copy_ids, start_date, due_date, reader=None):
    """Экземпляры из списка, занятые на интервал."""
    copy_ids = list(copy_ids)
    if not copy_ids:
        return set()

    loan_copy_ids = Loan.objects.filter(
        copy_id__in=copy_ids,
        status__in=BLOCKING_STATUSES,
        start_date__lt=due_date,
        due_date__gt=start_date,
    ).values_list("copy_id", flat=True)

    holds = Reservation.objects.filter(
        hold_copy_id__in=copy_ids,
        status=Reservation.Status.READY,
        hold_until__gt=timezone.now(),
    )
    if reader is not None and getattr(reader, "is_authenticated", False):
        # Своё удержание не мешает читателю оформить бронь.
        holds = holds.exclude(reader=reader)
    hold_copy_ids = holds.values_list("hold_copy_id", flat=True)

    return set(loan_copy_ids) | set(hold_copy_ids)


def attach_counts(books, start_date, due_date, reader=None):
    """Проставить книгам `total_copies`, `free_copies` и `busy_copies`.

    Один запрос за экземплярами и один за занятыми — без запросов на книгу.
    """
    books = list(books)
    if not books:
        return books

    copies = list(
        BookCopy.objects.filter(
            book_id__in=[book.id for book in books], is_active=True
        ).values("id", "book_id")
    )
    copies_by_book = defaultdict(list)
    for copy in copies:
        copies_by_book[copy["book_id"]].append(copy["id"])

    busy = busy_copy_ids(
        [copy["id"] for copy in copies], start_date, due_date, reader
    )

    for book in books:
        copy_ids = copies_by_book.get(book.id, [])
        free_ids = [copy_id for copy_id in copy_ids if copy_id not in busy]
        book.total_copies = len(copy_ids)
        book.free_copies = len(free_ids)
        book.busy_copies = len(copy_ids) - len(free_ids)
        book.free_copy_ids = free_ids
        book.counts_attached = True

    return books


def describe(book, start_date, due_date, reader=None):
    """Полная доступность книги: счётчики и список активных экземпляров.

    Просроченные удержания гасятся здесь же: фоновых задач нет, а именно
    проверка доступности должна освободить экземпляр для следующего.
    """
    expire_outdated_holds(book.id)
    copies = list(book.copies.filter(is_active=True).order_by("inventory_number"))
    busy = busy_copy_ids(
        [copy.id for copy in copies], start_date, due_date, reader
    )

    items = [
        {
            "id": copy.id,
            "inventory_number": copy.inventory_number,
            "condition": copy.condition,
            "is_available": copy.id not in busy,
        }
        for copy in copies
    ]
    free_items = [item for item in items if item["is_available"]]

    return {
        "total_copies": len(items),
        "free_copies": len(free_items),
        "busy_copies": len(items) - len(free_items),
        "is_available": bool(free_items),
        "available_copies": free_items,
        "copies": items,
        "my_loan": _my_loan(book, start_date, due_date, reader),
    }


def _my_loan(book, start_date, due_date, reader):
    """Действующая бронь читателя на эту книгу в выбранном периоде."""
    if reader is None or not getattr(reader, "is_authenticated", False):
        return None

    loan = (
        Loan.objects.filter(
            reader=reader,
            copy__book=book,
            status__in=BLOCKING_STATUSES,
            start_date__lt=due_date,
            due_date__gt=start_date,
        )
        .order_by("start_date", "id")
        .first()
    )
    if loan is None:
        return None
    return {
        "id": loan.id,
        "status": loan.status,
        "start_date": loan.start_date,
        "due_date": loan.due_date,
    }
