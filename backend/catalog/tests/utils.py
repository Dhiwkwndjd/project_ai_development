"""Общие помощники тестов каталога."""

from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import Book, BookCopy
from loans.models import Loan
from loans.statuses import LoanStatus
from reservations.models import Reservation
from users.models import User

PASSWORD = "StrongPass123!"


def make_user(email, role=User.Role.READER):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name="Тестовый Пользователь", role=role
    )


def make_book(
    title="Тестовая книга",
    author="Тестовый Автор",
    genre="Роман",
    is_active=True,
):
    return Book.objects.create(
        title=title, author=author, genre=genre, is_active=is_active
    )


def make_copy(book, number="INV-T-001", is_active=True):
    return BookCopy.objects.create(
        book=book, inventory_number=number, is_active=is_active
    )


def make_loan(copy, reader, start, due, status=LoanStatus.CREATED):
    return Loan.objects.create(
        reader=reader, copy=copy, start_date=start, due_date=due, status=status
    )


def make_hold(book, copy, reader, hold_until=None):
    return Reservation.objects.create(
        book=book,
        reader=reader,
        status=Reservation.Status.READY,
        hold_copy=copy,
        hold_until=hold_until or timezone.now() + timedelta(hours=48),
    )


def find_book(results, book_id):
    return next(item for item in results if item["id"] == book_id)


class AuthMixin:
    """Авторизация запросов теста access-токеном."""

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
