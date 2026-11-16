"""SQL-агрегация отчётов и подготовка CSV-выгрузок.

Период у книг ставится в условие ON через FilteredRelation: книги без
выдач остаются в результате (LEFT JOIN), а не исчезают из-за WHERE.
"""

import csv
import io
from datetime import datetime, time, timedelta

from django.db.models import Count, FilteredRelation, Q
from django.utils import timezone

from catalog.models import Book
from loans.models import Loan, LoanStatusHistory
from loans.statuses import LoanStatus
from reservations.models import Reservation

TOP_BOOKS_LIMIT = 5
# Популярность считаем по состоявшимся бронированиям, отменённые не берём.
POPULAR_STATUSES = (
    LoanStatus.CREATED,
    LoanStatus.ACTIVE,
    LoanStatus.RETURNED,
)


def period_bounds(date_from, date_to):
    """Границы периода как aware datetime (конец — не включительно)."""
    current = timezone.get_current_timezone()
    start = None
    end = None
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), current)
    if date_to:
        end = timezone.make_aware(
            datetime.combine(date_to + timedelta(days=1), time.min), current
        )
    return start, end


def event_totals(date_from, date_to):
    """Выдачи, возвраты, отмены и заявки за период одним SQL-агрегатом."""
    start, end = period_bounds(date_from, date_to)

    history = LoanStatusHistory.objects.all()
    if start:
        history = history.filter(created_at__gte=start)
    if end:
        history = history.filter(created_at__lt=end)

    totals = history.aggregate(
        issued=Count("id", filter=Q(new_status=LoanStatus.ACTIVE)),
        returned=Count("id", filter=Q(new_status=LoanStatus.RETURNED)),
        cancelled=Count("id", filter=Q(new_status=LoanStatus.CANCELLED)),
    )

    reservations = Reservation.objects.all()
    if start:
        reservations = reservations.filter(created_at__gte=start)
    if end:
        reservations = reservations.filter(created_at__lt=end)
    totals["reservations"] = reservations.count()
    return totals


def books_with_period_loans(date_from, date_to):
    """Книги с числом броней за период; книги без броней тоже попадают."""
    condition = Q(copies__loans__status__in=POPULAR_STATUSES)
    if date_from:
        condition &= Q(copies__loans__due_date__gt=date_from)
    if date_to:
        condition &= Q(copies__loans__start_date__lte=date_to)

    period_loans = FilteredRelation("copies__loans", condition=condition)
    return (
        Book.objects.annotate(period_loans=period_loans)
        .annotate(
            copies_total=Count("copies", distinct=True),
            copies_used=Count("period_loans__copy", distinct=True),
            loans_count=Count("period_loans"),
        )
        .order_by("-loans_count", "title", "id")
    )


def build_book_load(date_from, date_to):
    """Строки таблицы загрузки: все книги, включая нулевые значения."""
    rows = []
    for book in books_with_period_loans(date_from, date_to):
        copies = book.copies_total
        # Загрузка — доля экземпляров, участвовавших в выдачах за период.
        load = round(book.copies_used / copies * 100, 1) if copies else 0.0
        rows.append(
            {
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "copies_total": copies,
                "copies_used": book.copies_used,
                "loans_count": book.loans_count,
                "load_percent": load,
            }
        )
    return rows


def build_summary(filters):
    """Ответ `/api/reports/summary/`."""
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    book_load = build_book_load(date_from, date_to)
    top_books = [row for row in book_load if row["loans_count"] > 0]

    return {
        "period": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "totals": event_totals(date_from, date_to),
        "top_books": top_books[:TOP_BOOKS_LIMIT],
        "book_load": book_load,
    }


FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_cell(value):
    """Не дать Excel выполнить формулу из названия книги или ФИО."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def build_csv(headers, rows):
    """CSV в UTF-8 с BOM: Excel корректно показывает кириллицу."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([safe_csv_cell(value) for value in headers])
    writer.writerows(
        [safe_csv_cell(value) for value in row] for row in rows
    )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def loans_csv(date_from=None, date_to=None):
    """Выгрузка броней, пересекающихся с периодом."""
    loans = Loan.objects.select_related("reader", "copy__book").order_by(
        "-created_at", "-id"
    )
    if date_from:
        loans = loans.filter(due_date__gt=date_from)
    if date_to:
        loans = loans.filter(start_date__lte=date_to)

    rows = [
        [
            loan.id,
            loan.reader.full_name,
            loan.reader.email,
            loan.copy.book.title,
            loan.copy.book.author,
            loan.copy.inventory_number,
            loan.start_date.isoformat(),
            loan.due_date.isoformat(),
            loan.get_status_display(),
            timezone.localtime(loan.created_at).strftime("%d.%m.%Y %H:%M"),
        ]
        for loan in loans
    ]
    headers = [
        "ID",
        "Читатель",
        "Email",
        "Книга",
        "Автор",
        "Экземпляр",
        "Дата начала",
        "Дата возврата",
        "Статус",
        "Создана",
    ]
    return build_csv(headers, rows)


def books_csv():
    """Выгрузка всего фонда с количеством экземпляров."""
    books = (
        Book.objects.annotate(
            copies_total=Count("copies", distinct=True),
            copies_active=Count(
                "copies", filter=Q(copies__is_active=True), distinct=True
            ),
        ).order_by("title", "id")
    )
    rows = [
        [
            book.id,
            book.title,
            book.author,
            book.genre,
            book.year or "",
            "да" if book.is_active else "нет",
            book.copies_total,
            book.copies_active,
        ]
        for book in books
    ]
    headers = [
        "ID",
        "Название",
        "Автор",
        "Жанр",
        "Год",
        "В каталоге",
        "Всего экземпляров",
        "Доступных экземпляров",
    ]
    return build_csv(headers, rows)
