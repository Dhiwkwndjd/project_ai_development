"""Возврат книги, удержание на 48 часов и истечение срока."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.tests.utils import (
    AuthMixin,
    make_book,
    make_copy,
    make_hold,
    make_loan,
    make_user,
)
from loans.models import Loan, LoanStatusHistory
from loans.statuses import LoanStatus
from reservations.models import Reservation
from reservations.services import HOLD_HOURS
from users.models import ActivityLog, User

LOANS_URL = "/api/loans/"
BOOKS_URL = "/api/books/"


class ReturnAndHoldTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.book = make_book(title="Книга удержания")
        self.copy = make_copy(self.book)
        self.owner = make_user("owner@test.local")
        self.first = make_user("first@test.local")
        self.second = make_user("second@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.active_loan = make_loan(
            self.copy,
            self.owner,
            self.today - timedelta(days=2),
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )
        self.authenticate(self.librarian)

    def change_status(self, loan, new_status):
        return self.client.patch(
            f"{LOANS_URL}{loan.id}/status/",
            {"status": new_status},
            format="json",
        )

    def availability(self, reader):
        self.authenticate(reader)
        return self.client.get(f"{BOOKS_URL}{self.book.id}/availability/")

    def test_return_makes_first_waiting_ready_for_48_hours(self):
        first = Reservation.objects.create(book=self.book, reader=self.first)
        second = Reservation.objects.create(book=self.book, reader=self.second)

        response = self.change_status(self.active_loan, LoanStatus.RETURNED)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_loan.refresh_from_db()
        self.assertEqual(self.active_loan.status, LoanStatus.RETURNED)

        first.refresh_from_db()
        self.assertEqual(first.status, Reservation.Status.READY)
        self.assertEqual(first.hold_copy, self.copy)
        self.assertIsNotNone(first.hold_until)
        delta = first.hold_until - timezone.now()
        self.assertGreater(delta, timedelta(hours=HOLD_HOURS - 1))
        self.assertLessEqual(delta, timedelta(hours=HOLD_HOURS))

        second.refresh_from_db()
        self.assertEqual(second.status, Reservation.Status.WAITING)

    def test_return_writes_history_and_activity_log(self):
        Reservation.objects.create(book=self.book, reader=self.first)

        self.change_status(self.active_loan, LoanStatus.RETURNED)

        history = LoanStatusHistory.objects.filter(loan=self.active_loan).latest(
            "created_at"
        )
        self.assertEqual(history.old_status, LoanStatus.ACTIVE)
        self.assertEqual(history.new_status, LoanStatus.RETURNED)
        self.assertEqual(history.changed_by, self.librarian)

        log = ActivityLog.objects.filter(
            action=ActivityLog.Action.LOAN_STATUS_CHANGED,
            entity_type="loan",
            entity_id=self.active_loan.id,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.librarian)

        ready_log = ActivityLog.objects.filter(
            action=ActivityLog.Action.RESERVATION_READY
        ).first()
        self.assertIsNotNone(ready_log)
        self.assertEqual(ready_log.user, self.first)

    def test_return_without_queue_keeps_copy_free(self):
        response = self.change_status(self.active_loan, LoanStatus.RETURNED)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            Reservation.objects.filter(status=Reservation.Status.READY).exists()
        )

    def test_expired_hold_moves_to_next_on_availability_check(self):
        expired = make_hold(
            self.book,
            self.copy,
            self.first,
            hold_until=timezone.now() - timedelta(hours=1),
        )
        next_in_queue = Reservation.objects.create(
            book=self.book, reader=self.second
        )

        response = self.availability(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expired.refresh_from_db()
        self.assertEqual(expired.status, Reservation.Status.EXPIRED)
        next_in_queue.refresh_from_db()
        self.assertEqual(next_in_queue.status, Reservation.Status.READY)
        self.assertEqual(next_in_queue.hold_copy, self.copy)
        self.assertGreater(next_in_queue.hold_until, timezone.now())

    def test_expired_hold_does_not_move_without_waiting(self):
        expired = make_hold(
            self.book,
            self.copy,
            self.first,
            hold_until=timezone.now() - timedelta(hours=1),
        )

        response = self.availability(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expired.refresh_from_db()
        self.assertEqual(expired.status, Reservation.Status.EXPIRED)
        self.assertFalse(
            Reservation.objects.filter(status=Reservation.Status.READY).exists()
        )

    def test_full_scenario_queue_return_hold_and_fulfillment(self):
        # 1. Свободных экземпляров нет, первый читатель встаёт в очередь.
        self.authenticate(self.first)
        queue_response = self.client.post(
            "/api/reservations/", {"book_id": self.book.id}, format="json"
        )
        self.assertEqual(queue_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(queue_response.data["position"], 1)

        # 2. Второй читатель — за ним.
        self.authenticate(self.second)
        second_queue = self.client.post(
            "/api/reservations/", {"book_id": self.book.id}, format="json"
        )
        self.assertEqual(second_queue.data["position"], 2)

        # 3. Библиотекарь принимает возврат: экземпляр уходит первому.
        self.authenticate(self.librarian)
        self.change_status(self.active_loan, LoanStatus.RETURNED)
        first_reservation = Reservation.objects.get(
            book=self.book, reader=self.first
        )
        self.assertEqual(first_reservation.status, Reservation.Status.READY)
        self.assertEqual(first_reservation.hold_copy, self.copy)

        # 4. Первый оформляет бронь на удержанный экземпляр.
        self.authenticate(self.first)
        start = self.today
        due = self.today + timedelta(days=10)
        loan_response = self.client.post(
            LOANS_URL,
            {
                "copy_id": self.copy.id,
                "start_date": start.isoformat(),
                "due_date": due.isoformat(),
            },
            format="json",
        )
        self.assertEqual(loan_response.status_code, status.HTTP_201_CREATED)
        first_reservation.refresh_from_db()
        self.assertEqual(first_reservation.status, Reservation.Status.FULFILLED)

        # 5. Библиотекарь выдаёт бронь и принимает возврат — удержание
        # переходит второму читателю.
        first_loan = Loan.objects.get(pk=loan_response.data["id"])
        self.authenticate(self.librarian)
        issue = self.change_status(first_loan, LoanStatus.ACTIVE)
        self.assertEqual(issue.status_code, status.HTTP_200_OK)
        back = self.change_status(first_loan, LoanStatus.RETURNED)
        self.assertEqual(back.status_code, status.HTTP_200_OK)

        second_reservation = Reservation.objects.get(
            book=self.book, reader=self.second
        )
        self.assertEqual(second_reservation.status, Reservation.Status.READY)
        self.assertEqual(second_reservation.hold_copy, self.copy)
