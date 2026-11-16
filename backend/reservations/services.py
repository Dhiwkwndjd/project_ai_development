"""FIFO-очередь читателей и удержание экземпляров.

Порядок обслуживания: `ORDER BY created_at, id`. Все операции, меняющие
очередь, выполняются в транзакции и блокируют строку книги — иначе два
одновременных возврата могли бы выдать одно удержание двум читателям.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from catalog.models import Book
from reservations.models import Reservation
from users.models import ActivityLog, User
from users.services import log_action

HOLD_HOURS = 48


class ReservationError(Exception):
    """Ошибка бизнес-правила очереди: код ответа и сообщение."""

    def __init__(self, detail, code, status_code=400):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


@transaction.atomic
def create_reservation(*, reader, book_id, request=None):
    """Поставить читателя в очередь на книгу.

    Читатель всегда приходит из проверенного JWT. Повторная активная
    заявка на ту же книгу запрещена.
    """
    book = _lock_book(book_id, active_only=True)
    if book is None:
        raise ReservationError("Книга не найдена", "not_found", 404)

    expire_outdated_holds_locked(book)

    if Reservation.objects.filter(
        book=book,
        reader=reader,
        status__in=Reservation.ACTIVE_STATUSES,
    ).exists():
        raise ReservationError(
            "Вы уже стоите в очереди на эту книгу", "already_queued", 409
        )

    reservation = Reservation.objects.create(book=book, reader=reader)
    log_action(
        request,
        reader,
        ActivityLog.Action.RESERVATION_CREATED,
        description=f"Очередь на «{book.title}»",
        entity=reservation,
    )
    return reservation


def expire_outdated_holds(book_id):
    """Погасить просроченные удержания книги и передать экземпляры дальше.

    Фоновых задач нет, поэтому проверка выполняется при обращении к API.
    """
    with transaction.atomic():
        book = _lock_book(book_id)
        if book is None:
            return []
        return expire_outdated_holds_locked(book)


def expire_outdated_holds_locked(book):
    """Версия для вызова внутри уже открытой транзакции с блокировкой книги."""
    now = timezone.now()
    expired = list(
        Reservation.objects.select_for_update()
        .filter(book=book, status=Reservation.Status.READY, hold_until__lte=now)
        .order_by("created_at", "id")
    )

    for reservation in expired:
        copy = reservation.hold_copy
        reservation.status = Reservation.Status.EXPIRED
        reservation.save(update_fields=["status", "updated_at"])
        log_action(
            None,
            None,
            ActivityLog.Action.RESERVATION_EXPIRED,
            description=f"Удержание «{book.title}» истекло",
            entity=reservation,
        )
        if copy is not None:
            assign_hold_to_next(book, copy)

    return expired


def assign_hold_to_next(book, copy):
    """Отдать освободившийся экземпляр первому ожидающему.

    Вызывается внутри транзакции, которая уже заблокировала строку книги.
    """
    if copy is None:
        return None

    already_held = Reservation.objects.filter(
        hold_copy=copy, status=Reservation.Status.READY
    ).exists()
    if already_held:
        return None

    reservation = (
        Reservation.objects.select_for_update()
        .filter(book=book, status=Reservation.Status.WAITING)
        .order_by("created_at", "id")
        .first()
    )
    if reservation is None:
        return None

    reservation.status = Reservation.Status.READY
    reservation.hold_copy = copy
    reservation.hold_until = timezone.now() + timedelta(hours=HOLD_HOURS)
    reservation.save(
        update_fields=["status", "hold_copy", "hold_until", "updated_at"]
    )
    log_action(
        None,
        reservation.reader,
        ActivityLog.Action.RESERVATION_READY,
        description=(
            f"Экземпляр {copy.inventory_number} удержан за читателем "
            f"до {reservation.hold_until:%d.%m.%Y %H:%M}"
        ),
        entity=reservation,
    )
    return reservation


def fulfill_reservation(reader, book, copy=None, request=None):
    """Закрыть заявку `ready`, когда читатель оформил бронь этой книги.

    Если читатель взял другой экземпляр, удержанный экземпляр сразу
    переходит следующему в очереди: иначе он простаивает, а очередь
    ждёт возврата, которого уже не будет.
    """
    reservation = (
        Reservation.objects.select_for_update()
        .filter(book=book, reader=reader, status=Reservation.Status.READY)
        .order_by("created_at", "id")
        .first()
    )
    if reservation is None:
        return None

    held_copy = reservation.hold_copy
    reservation.status = Reservation.Status.FULFILLED
    reservation.hold_copy = None
    reservation.hold_until = None
    reservation.save(
        update_fields=["status", "hold_copy", "hold_until", "updated_at"]
    )
    log_action(
        request,
        reader,
        ActivityLog.Action.RESERVATION_FULFILLED,
        description=f"Заявка на «{book.title}» выполнена",
        entity=reservation,
    )
    if held_copy is not None and copy is not None and held_copy.pk != copy.pk:
        assign_hold_to_next(book, held_copy)
    return reservation


def cancel_reservation(reservation_id, actor, request=None):
    """Отменить заявку: владелец или администратор.

    Если отменяется удержание, экземпляр сразу переходит следующему
    ожидающему.
    """
    target = (
        Reservation.objects.filter(pk=reservation_id)
        .values("id", "book_id", "reader_id")
        .first()
    )
    if target is None:
        raise ReservationError("Заявка не найдена", "not_found", 404)
    if target["reader_id"] != actor.id and actor.role != User.Role.ADMIN:
        raise ReservationError("Заявка не найдена", "not_found", 404)

    with transaction.atomic():
        # Сначала книга, потом заявка — тот же порядок, что при возврате.
        book = _lock_book(target["book_id"])
        reservation = (
            Reservation.objects.select_for_update()
            .select_related("hold_copy")
            .filter(pk=reservation_id)
            .first()
        )
        if reservation is None or book is None:
            raise ReservationError("Заявка не найдена", "not_found", 404)
        if reservation.status not in Reservation.ACTIVE_STATUSES:
            raise ReservationError("Заявка уже закрыта", "bad_transition", 409)

        copy = reservation.hold_copy
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])
        log_action(
            request,
            actor,
            ActivityLog.Action.RESERVATION_CANCELLED,
            description=f"Заявка на «{book.title}» отменена",
            entity=reservation,
        )
        if copy is not None:
            assign_hold_to_next(book, copy)

    return reservation


def queue_position(reservation):
    """Позиция в очереди: 1 — следующий на обслуживание."""
    if reservation.status == Reservation.Status.WAITING:
        earlier = Reservation.objects.filter(
            book_id=reservation.book_id,
            status=Reservation.Status.WAITING,
        ).filter(
            Q(created_at__lt=reservation.created_at)
            | Q(created_at=reservation.created_at, id__lt=reservation.id)
        )
        return earlier.count() + 1
    if reservation.status == Reservation.Status.READY:
        return 1
    return None


def queue_state(book, reader=None):
    """Счётчики очереди и активная заявка читателя на книгу."""
    active = Reservation.objects.filter(
        book=book, status__in=Reservation.ACTIVE_STATUSES
    )
    my_reservation = None
    if reader is not None and getattr(reader, "is_authenticated", False):
        my_reservation = (
            active.filter(reader=reader).select_related("book").first()
        )
    return {
        "waiting_count": active.filter(status=Reservation.Status.WAITING).count(),
        "queue_length": active.count(),
        "my_reservation": my_reservation,
    }


def expire_reader_holds(reader):
    """Погасить просроченные удержания читателя перед выдачей его списка."""
    book_ids = (
        Reservation.objects.filter(
            reader=reader,
            status=Reservation.Status.READY,
            hold_until__lte=timezone.now(),
        )
        .values_list("book_id", flat=True)
        .distinct()
    )
    for book_id in list(book_ids):
        expire_outdated_holds(book_id)


def expire_all_outdated_holds():
    """Погасить все просроченные удержания перед выдачей очереди сотруднику."""
    book_ids = (
        Reservation.objects.filter(
            status=Reservation.Status.READY,
            hold_until__lte=timezone.now(),
        )
        .values_list("book_id", flat=True)
        .distinct()
    )
    for book_id in list(book_ids):
        expire_outdated_holds(book_id)


def _lock_book(book_id, active_only=False):
    queryset = Book.objects.select_for_update()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.filter(pk=book_id).first()
