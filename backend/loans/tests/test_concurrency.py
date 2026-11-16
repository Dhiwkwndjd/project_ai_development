"""Тест конкурентности: 10 одновременных бронирований одного экземпляра.

На SQLite гарантию даёт `transaction_mode="IMMEDIATE"` в настройках: транзакция
берёт блокировку записи до чтения, поэтому проверка пересечений и INSERT не
расходятся между потоками. Тестовая база — файл (`TEST.NAME`), иначе потоки
получают `database table is locked` на in-memory базе с shared cache. Запуск:
    python manage.py test loans.tests.test_concurrency -v 2
"""

import threading

from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import Book, BookCopy
from loans.models import Loan, LoanStatusHistory
from users.models import ActivityLog, User

LOANS_URL = "/api/loans/"
THREADS = 10


class ConcurrentBookingTests(TransactionTestCase):
    def setUp(self):
        self.book = Book.objects.create(
            title="Гонка за книгой", author="Тестовый Автор", genre="Роман"
        )
        self.copy = BookCopy.objects.create(
            book=self.book, inventory_number="INV-RACE-001"
        )
        self.reader = User.objects.create_user(
            email="race@test.local", password="StrongPass123!", full_name="Читатель Гонки"
        )
        self.access = str(RefreshToken.for_user(self.reader).access_token)

    def book_copy(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        return client.post(
            LOANS_URL,
            {"copy_id": self.copy.id, "start_date": "2030-01-10"},
            format="json",
        )

    def test_ten_parallel_requests_create_exactly_one_loan(self):
        results = []
        errors = []
        lock = threading.Lock()
        barrier = threading.Barrier(THREADS)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                response = self.book_copy()
                with lock:
                    results.append((response.status_code, response.data.get("code")))
            except Exception as error:  # noqa: BLE001 — нужен текст для диагностики
                with lock:
                    errors.append(repr(error))
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertFalse(errors, f"Ошибки в потоках: {errors}")
        self.assertEqual(len(results), THREADS)

        statuses = [status_code for status_code, _ in results]
        self.assertEqual(statuses.count(201), 1, f"Ответы: {results}")
        self.assertEqual(statuses.count(409), THREADS - 1, f"Ответы: {results}")

        for status_code, code in results:
            if status_code == 409:
                self.assertEqual(code, "copy_taken")

        self.assertEqual(Loan.objects.filter(copy=self.copy).count(), 1)
        self.assertEqual(LoanStatusHistory.objects.count(), 1)
        self.assertEqual(
            ActivityLog.objects.filter(action=ActivityLog.Action.LOAN_CREATED).count(), 1
        )
