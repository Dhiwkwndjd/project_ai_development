"""Матрица переходов статусов брони.

Правило хранится в одном месте: и API, и тесты, и демо-данные
проверяют переходы через эти функции.
"""

from django.db import models


class LoanStatus(models.TextChoices):
    CREATED = "created", "Создана"
    ACTIVE = "active", "Выдана"
    RETURNED = "returned", "Возвращена"
    CANCELLED = "cancelled", "Отменена"


TERMINAL_STATUSES = frozenset({LoanStatus.RETURNED, LoanStatus.CANCELLED})

ALLOWED_TRANSITIONS = {
    LoanStatus.CREATED: frozenset({LoanStatus.ACTIVE, LoanStatus.CANCELLED}),
    LoanStatus.ACTIVE: frozenset({LoanStatus.RETURNED}),
    LoanStatus.RETURNED: frozenset(),
    LoanStatus.CANCELLED: frozenset(),
}

# Статусы, при которых бронь занимает экземпляр.
BLOCKING_STATUSES = frozenset({LoanStatus.CREATED, LoanStatus.ACTIVE})


def can_transition(current, target):
    """Можно ли перевести бронь из current в target."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def is_terminal(status):
    return status in TERMINAL_STATUSES
