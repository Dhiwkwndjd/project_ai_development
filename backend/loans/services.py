"""Бизнес-логика создания брони.

Порядок строго такой: открыть транзакцию → взять экземпляр через
`SELECT ... FOR UPDATE` → проверить пересечения и удержания → вставить бронь.
Если поменять порядок, два читателя смогут забронировать один экземпляр.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalog.models import Book, BookCopy
from loans.models import Loan, LoanStatusHistory
from loans.statuses import BLOCKING_STATUSES, LoanStatus, can_transition
from reservations.models import Reservation
from reservations.services import (
    assign_hold_to_next,
    expire_outdated_holds_locked,
    fulfill_reservation,
)
from users.models import ActivityLog, User
from users.services import log_action

DEFAULT_LOAN_DAYS = 14
MAX_LOAN_DAYS = 30
MAX_START_AHEAD_DAYS = 365

NO_COPIES_DETAIL = "На эти даты нет свободных экземпляров. Можно встать в очередь."


class LoanError(Exception):
    """Ошибка бизнес-правила: превращается в ответ с кодом и статусом."""

    def __init__(self, detail, code, status_code=400):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


def resolve_period(start_date=None, due_date=None):
    """Проверить период брони и достроить недостающую дату.

    По умолчанию бронь на 14 дней, максимум 30, начало не в прошлом.
    """
    today = timezone.localdate()
    start = start_date or today

    if start < today:
        raise LoanError("Дата начала не может быть в прошлом", "invalid_period")
    if start > today + timedelta(days=MAX_START_AHEAD_DAYS):
        raise LoanError(
            f"Бронь можно начать не позже чем через {MAX_START_AHEAD_DAYS} дней",
            "invalid_period",
        )

    due = due_date or start + timedelta(days=DEFAULT_LOAN_DAYS)

    if due <= start:
        raise LoanError("Дата возврата должна быть позже даты начала", "invalid_period")
    if due - start > timedelta(days=MAX_LOAN_DAYS):
        raise LoanError(
            f"Максимальный срок брони — {MAX_LOAN_DAYS} дней", "invalid_period"
        )
    return start, due


def create_loan(
    *,
    reader,
    copy_id=None,
    book_id=None,
    start_date=None,
    due_date=None,
    comment="",
    request=None,
):
    """Создать бронь на экземпляр или на свободный экземпляр книги.

    Читатель всегда приходит из проверенного JWT, а не из тела запроса.
    """
    start, due = resolve_period(start_date, due_date)

    with transaction.atomic():
        # Первый запрос транзакции — блокировка строк экземпляров.
        copies = _lock_copies(copy_id, book_id)
        book = Book.objects.select_for_update().get(pk=copies[0].book_id)
        # Просроченные удержания не должны блокировать фонд и обходить очередь.
        expire_outdated_holds_locked(book)
        copy = _pick_free_copy(copies, start, due, reader, explicit=copy_id is not None)

        loan = Loan.objects.create(
            reader=reader,
            copy=copy,
            start_date=start,
            due_date=due,
            status=LoanStatus.CREATED,
            comment=comment,
        )
        LoanStatusHistory.objects.create(
            loan=loan,
            old_status="",
            new_status=LoanStatus.CREATED,
            changed_by=reader,
        )
        log_action(
            request,
            reader,
            ActivityLog.Action.LOAN_CREATED,
            description=f"Бронь «{copy.book.title}» на {start:%d.%m.%Y}–{due:%d.%m.%Y}",
            entity=loan,
        )
        # Читатель с удержанием получает книгу: заявка становится fulfilled.
        fulfill_reservation(reader, book, copy=copy, request=request)
        return loan


def _lock_copies(copy_id, book_id):
    """Заблокировать экземпляр (или все активные экземпляры книги) в транзакции."""
    if copy_id is not None:
        copy = BookCopy.objects.select_for_update().filter(pk=copy_id).first()
        if copy is None:
            raise LoanError("Экземпляр не найден", "not_found", 404)
        if not copy.is_active or not copy.book.is_active:
            raise LoanError(NO_COPIES_DETAIL, "no_copies", 409)
        return [copy]

    if book_id is None:
        raise LoanError("Укажите экземпляр или книгу", "target_required")

    copies = list(
        BookCopy.objects.select_for_update()
        .filter(book_id=book_id, is_active=True)
        .order_by("pk")
    )
    book = Book.objects.filter(pk=book_id).values("id", "is_active").first()
    if book is None:
        raise LoanError("Книга не найдена", "not_found", 404)
    if not book["is_active"] or not copies:
        raise LoanError(NO_COPIES_DETAIL, "no_copies", 409)
    return copies


def _pick_free_copy(copies, start, due, reader, explicit):
    """Вернуть первый свободный экземпляр из уже заблокированных."""
    for copy in copies:
        if not _is_copy_busy(copy, start, due, reader):
            return copy

    if explicit:
        raise LoanError("Экземпляр уже забронирован на эти даты", "copy_taken", 409)
    raise LoanError(NO_COPIES_DETAIL, "no_copies", 409)


def _is_copy_busy(copy, start, due, reader):
    """Занят ли экземпляр: пересекающаяся бронь или чужое действующее удержание."""
    overlaps = Loan.objects.filter(
        copy=copy,
        status__in=BLOCKING_STATUSES,
        start_date__lt=due,
        due_date__gt=start,
    ).exists()
    if overlaps:
        return True

    return (
        Reservation.objects.filter(
            hold_copy=copy,
            status=Reservation.Status.READY,
            hold_until__gt=timezone.now(),
        )
        .exclude(reader=reader)
        .exists()
    )


def change_loan_status(*, loan_id, new_status, actor, request=None):
    """Сменить статус брони по матрице переходов.

    Статус, история и журнал пишутся в одной транзакции. Возврат
    (`active → returned`) освобождает экземпляр и передаёт удержание
    первому ожидающему в очереди.
    """
    with transaction.atomic():
        loan = (
            Loan.objects.select_for_update()
            .select_related("copy__book")
            .filter(pk=loan_id)
            .first()
        )
        if loan is None:
            raise LoanError("Бронь не найдена", "not_found", 404)

        _ensure_status_allowed(loan, new_status, actor)

        if not can_transition(loan.status, new_status):
            raise LoanError(
                "Недопустимый переход статуса: "
                f"«{_status_label(loan.status)}» → «{_status_label(new_status)}»",
                "bad_transition",
                409,
            )

        book = None
        if new_status == LoanStatus.RETURNED:
            # Возврат и выдача удержания — одна транзакция с блокировкой книги.
            book = Book.objects.select_for_update().get(pk=loan.copy.book_id)

        old_status = loan.status
        loan.status = new_status
        loan.save(update_fields=["status", "updated_at"])
        LoanStatusHistory.objects.create(
            loan=loan,
            old_status=old_status,
            new_status=new_status,
            changed_by=actor,
        )
        log_action(
            request,
            actor,
            ActivityLog.Action.LOAN_STATUS_CHANGED,
            description=(
                f"Бронь «{loan.copy.book.title}»: "
                f"{_status_label(old_status)} → {_status_label(new_status)}"
            ),
            entity=loan,
        )

        if new_status == LoanStatus.RETURNED:
            expire_outdated_holds_locked(book)
            assign_hold_to_next(book, loan.copy)

        return loan


def _ensure_status_allowed(loan, new_status, actor):
    """Проверить право роли на выбранный переход."""
    if actor.role == User.Role.READER:
        if loan.reader_id != actor.id:
            # Чужой объект не раскрываем.
            raise LoanError("Бронь не найдена", "not_found", 404)
        if new_status != LoanStatus.CANCELLED:
            raise LoanError(
                "Читатель может только отменить свою бронь", "forbidden", 403
            )


def _status_label(status):
    labels = dict(LoanStatus.choices)
    return labels.get(status, status)

