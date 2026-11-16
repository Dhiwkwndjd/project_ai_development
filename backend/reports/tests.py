"""Тесты отчётов: агрегаты, период и CSV с BOM."""

import csv
import io
from datetime import date, datetime

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import Book, BookCopy
from loans.models import Loan, LoanStatusHistory
from loans.statuses import LoanStatus
from reservations.models import Reservation
from users.models import User

SUMMARY_URL = "/api/reports/summary/"
LOANS_CSV_URL = "/api/reports/loans.csv"
BOOKS_CSV_URL = "/api/reports/books.csv"

PASSWORD = "StrongPass123!"
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 1, 31)
PERIOD_FROM = {"date_from": PERIOD_START.isoformat(), "date_to": PERIOD_END.isoformat()}


def make_user(email, role):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name="Тестовый Пользователь", role=role
    )


def make_book(title, author="Автор"):
    return Book.objects.create(title=title, author=author, genre="Тест")


def make_copy(book, number):
    return BookCopy.objects.create(
        book=book, inventory_number=number, condition=BookCopy.Condition.GOOD
    )


def at(day, hour=12, month=1, year=2026):
    """Осведомлённое время в текущей таймзоне проекта."""
    naive = datetime(year, month, day, hour, 0)
    return timezone.make_aware(naive, timezone.get_current_timezone())


class ReportApiTests(APITestCase):
    """Сводка и CSV: доступ, цифры, период и кириллица."""

    def setUp(self):
        self.admin = make_user("admin@test.local", User.Role.ADMIN)
        self.librarian = make_user("librarian@test.local", User.Role.LIBRARIAN)
        self.reader = make_user("reader@test.local", User.Role.READER)

        self.book_a = make_book("Чистый код", "Роберт Мартин")
        self.book_b = make_book("Кириллица без выдач", "Иван Петров")
        self.copy_a1 = make_copy(self.book_a, "INV-A1")
        self.copy_a2 = make_copy(self.book_a, "INV-A2")
        self.copy_b1 = make_copy(self.book_b, "INV-B1")

        self.returned = self.add_loan(
            self.copy_a1,
            "2026-01-05",
            "2026-01-20",
            LoanStatus.RETURNED,
            [LoanStatus.ACTIVE, LoanStatus.RETURNED],
        )
        self.active = self.add_loan(
            self.copy_a2,
            "2026-01-01",
            "2026-02-01",
            LoanStatus.ACTIVE,
            [LoanStatus.ACTIVE],
        )
        self.old = self.add_loan(
            self.copy_a2,
            "2025-12-01",
            "2025-12-10",
            LoanStatus.RETURNED,
            [LoanStatus.ACTIVE, LoanStatus.RETURNED],
            changed_at=[at(1, month=12, year=2025), at(5, month=12, year=2025)],
        )
        self.cancelled = self.add_loan(
            self.copy_a1,
            "2026-02-01",
            "2026-02-10",
            LoanStatus.CANCELLED,
            [LoanStatus.CANCELLED],
            changed_at=[at(20)],
        )

        self.reservation = Reservation.objects.create(
            book=self.book_a, reader=self.reader
        )
        Reservation.objects.filter(pk=self.reservation.pk).update(created_at=at(15))
        self.old_reservation = Reservation.objects.create(
            book=self.book_b, reader=self.reader
        )
        Reservation.objects.filter(pk=self.old_reservation.pk).update(
            created_at=timezone.make_aware(
                datetime(2025, 12, 20, 12, 0), timezone.get_current_timezone()
            )
        )

    def add_loan(self, copy, start, due, final_status, transitions, changed_at=None):
        loan = Loan.objects.create(
            reader=self.reader,
            copy=copy,
            start_date=date.fromisoformat(start),
            due_date=date.fromisoformat(due),
            status=final_status,
        )
        moments = changed_at or [at(10)] * len(transitions)
        for index, new_status in enumerate(transitions):
            history = LoanStatusHistory.objects.create(
                loan=loan,
                old_status="",
                new_status=new_status,
                changed_by=self.librarian,
            )
            LoanStatusHistory.objects.filter(pk=history.pk).update(
                created_at=moments[index]
            )
        return loan

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_reports_require_admin(self):
        for user in (self.reader, self.librarian):
            self.authenticate(user)
            for url in (SUMMARY_URL, LOANS_CSV_URL, BOOKS_CSV_URL):
                response = self.client.get(url, PERIOD_FROM)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.admin)
        for url in (SUMMARY_URL, LOANS_CSV_URL, BOOKS_CSV_URL):
            response = self.client.get(url, PERIOD_FROM)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_period_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.get(
            SUMMARY_URL, {"date_from": "2026-02-01", "date_to": "2026-01-01"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_summary_counts_match_sql(self):
        self.authenticate(self.admin)

        response = self.client.get(SUMMARY_URL, PERIOD_FROM)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        totals = response.data["totals"]
        self.assertEqual(totals["issued"], 2)
        self.assertEqual(totals["returned"], 1)
        self.assertEqual(totals["cancelled"], 1)
        self.assertEqual(totals["reservations"], 1)

        start = timezone.make_aware(
            datetime(2026, 1, 1), timezone.get_current_timezone()
        )
        end = timezone.make_aware(
            datetime(2026, 2, 1), timezone.get_current_timezone()
        )
        with connection.cursor() as cursor:
            for key, new_status in (
                ("issued", LoanStatus.ACTIVE),
                ("returned", LoanStatus.RETURNED),
                ("cancelled", LoanStatus.CANCELLED),
            ):
                cursor.execute(
                    "SELECT COUNT(*) FROM loan_status_history "
                    "WHERE new_status = %s AND created_at >= %s AND created_at < %s",
                    [new_status.value, start, end],
                )
                self.assertEqual(totals[key], cursor.fetchone()[0])
            cursor.execute(
                "SELECT COUNT(*) FROM reservations "
                "WHERE created_at >= %s AND created_at < %s",
                [start, end],
            )
            self.assertEqual(totals["reservations"], cursor.fetchone()[0])

    def test_top_books_match_sql_and_keep_books_without_loans(self):
        self.authenticate(self.admin)

        response = self.client.get(SUMMARY_URL, PERIOD_FROM)

        top = {item["book_id"]: item for item in response.data["top_books"]}
        load = {item["book_id"]: item for item in response.data["book_load"]}
        self.assertEqual(top[self.book_a.id]["loans_count"], 2)
        self.assertNotIn(self.book_b.id, top)
        self.assertEqual(load[self.book_a.id]["copies_used"], 2)
        self.assertEqual(load[self.book_a.id]["load_percent"], 100.0)
        self.assertEqual(load[self.book_b.id]["loans_count"], 0)
        self.assertEqual(load[self.book_b.id]["copies_used"], 0)
        self.assertEqual(load[self.book_b.id]["copies_total"], 1)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT b.id, COUNT(l.id) FROM books b "
                "LEFT JOIN book_copies c ON c.book_id = b.id "
                "LEFT JOIN loans l ON l.copy_id = c.id "
                "AND l.status IN ('created', 'active', 'returned') "
                "AND l.start_date <= %s AND l.due_date > %s "
                "GROUP BY b.id",
                [PERIOD_END, PERIOD_START],
            )
            sql_counts = dict(cursor.fetchall())
        self.assertEqual(top[self.book_a.id]["loans_count"], sql_counts[self.book_a.id])
        self.assertEqual(load[self.book_b.id]["loans_count"], sql_counts[self.book_b.id])

    def test_loans_csv_has_bom_and_cyrillic(self):
        self.authenticate(self.admin)

        response = self.client.get(LOANS_CSV_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("loans.csv", response["Content-Disposition"])
        text = response.content.decode("utf-8-sig")
        self.assertIn("Чистый код", text)
        self.assertIn("Читатель", text)

    def test_loans_csv_filters_by_period(self):
        self.authenticate(self.admin)

        response = self.client.get(LOANS_CSV_URL, PERIOD_FROM)

        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        ids = {int(row[0]) for row in rows[1:]}
        self.assertIn(self.returned.id, ids)
        self.assertIn(self.active.id, ids)
        self.assertNotIn(self.old.id, ids)
        self.assertNotIn(self.cancelled.id, ids)

    def test_books_csv_escapes_formula_cells(self):
        make_book('=HYPERLINK("http://evil.example")', "Опасный Автор")
        self.authenticate(self.admin)

        response = self.client.get(BOOKS_CSV_URL)

        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        titles = {row[1] for row in rows[1:]}
        self.assertIn('\'=HYPERLINK("http://evil.example")', titles)
        self.assertNotIn('=HYPERLINK("http://evil.example")', titles)

    def test_books_csv_has_bom_and_all_books(self):
        self.authenticate(self.admin)

        response = self.client.get(BOOKS_CSV_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("books.csv", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        titles = {row[1] for row in rows[1:]}
        self.assertIn("Чистый код", titles)
        self.assertIn("Кириллица без выдач", titles)
