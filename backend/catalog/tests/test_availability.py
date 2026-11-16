"""Расчёт свободных экземпляров на интервал."""

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
from loans.statuses import LoanStatus
from users.models import User

BOOKS_URL = "/api/books/"


class BookAvailabilityTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)
        self.book = make_book(title="Книга доступности")
        self.first = make_copy(self.book, "INV-A-001")
        self.second = make_copy(self.book, "INV-A-002")
        self.third = make_copy(self.book, "INV-A-003")
        self.authenticate(self.reader)

    def availability(self, **params):
        return self.client.get(f"{BOOKS_URL}{self.book.id}/availability/", params)

    def test_default_period_is_fourteen_days(self):
        response = self.availability()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["book_id"], self.book.id)
        self.assertEqual(response.data["start_date"], self.today.isoformat())
        self.assertEqual(
            response.data["due_date"],
            (self.today + timedelta(days=14)).isoformat(),
        )
        self.assertEqual(response.data["total_copies"], 3)
        self.assertEqual(response.data["free_copies"], 3)
        self.assertEqual(response.data["busy_copies"], 0)
        self.assertTrue(response.data["is_available"])

    def test_start_only_fills_due_date(self):
        start = self.today + timedelta(days=5)

        response = self.availability(start_date=start.isoformat())

        self.assertEqual(response.data["start_date"], start.isoformat())
        self.assertEqual(response.data["due_date"], (start + timedelta(days=14)).isoformat())

    def test_active_loan_blocks_copy(self):
        make_loan(
            self.first,
            self.other,
            self.today,
            self.today + timedelta(days=10),
            status=LoanStatus.ACTIVE,
        )

        response = self.availability(
            start_date=(self.today + timedelta(days=2)).isoformat(),
            due_date=(self.today + timedelta(days=12)).isoformat(),
        )

        self.assertEqual(response.data["free_copies"], 2)
        self.assertEqual(response.data["busy_copies"], 1)
        self.assertEqual(
            {item["id"] for item in response.data["available_copies"]},
            {self.second.id, self.third.id},
        )

    def test_created_loan_also_blocks_copy(self):
        make_loan(
            self.first,
            self.other,
            self.today + timedelta(days=3),
            self.today + timedelta(days=8),
            status=LoanStatus.CREATED,
        )

        response = self.availability(
            start_date=(self.today + timedelta(days=4)).isoformat(),
            due_date=(self.today + timedelta(days=7)).isoformat(),
        )

        self.assertEqual(response.data["free_copies"], 2)

    def test_reader_own_loan_reported_in_period(self):
        own = make_loan(
            self.first,
            self.reader,
            self.today,
            self.today + timedelta(days=10),
        )

        response = self.availability()

        self.assertIsNotNone(response.data["my_loan"])
        self.assertEqual(response.data["my_loan"]["id"], own.id)
        self.assertEqual(response.data["my_loan"]["status"], LoanStatus.CREATED)

    def test_other_reader_loan_is_not_reported(self):
        make_loan(
            self.first,
            self.other,
            self.today,
            self.today + timedelta(days=10),
        )

        response = self.availability()

        self.assertIsNone(response.data["my_loan"])

    def test_loan_outside_period_is_not_reported(self):
        make_loan(
            self.first,
            self.reader,
            self.today + timedelta(days=40),
            self.today + timedelta(days=45),
        )

        response = self.availability()

        self.assertIsNone(response.data["my_loan"])

    def test_returned_and_cancelled_loans_do_not_block(self):
        for index, copy in enumerate((self.first, self.second)):
            make_loan(
                copy,
                self.other,
                self.today,
                self.today + timedelta(days=10),
                status=LoanStatus.RETURNED if index == 0 else LoanStatus.CANCELLED,
            )

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 3)

    def test_adjacent_intervals_do_not_overlap(self):
        start = self.today + timedelta(days=1)
        make_loan(
            self.first,
            self.other,
            start,
            start + timedelta(days=10),
            status=LoanStatus.ACTIVE,
        )

        response = self.availability(
            start_date=(start + timedelta(days=10)).isoformat(),
            due_date=(start + timedelta(days=20)).isoformat(),
        )

        self.assertEqual(response.data["free_copies"], 3)

        overlapping = self.availability(
            start_date=(start + timedelta(days=9)).isoformat(),
            due_date=(start + timedelta(days=20)).isoformat(),
        )
        self.assertEqual(overlapping.data["free_copies"], 2)

    def test_interval_touching_loan_start_is_free(self):
        make_loan(
            self.first,
            self.other,
            self.today + timedelta(days=5),
            self.today + timedelta(days=15),
            status=LoanStatus.ACTIVE,
        )

        response = self.availability(
            start_date=self.today.isoformat(),
            due_date=(self.today + timedelta(days=5)).isoformat(),
        )

        self.assertEqual(response.data["free_copies"], 3)

    def test_other_reader_hold_blocks_copy(self):
        make_hold(self.book, self.first, self.other)

        response = self.availability(
            start_date=(self.today + timedelta(days=5)).isoformat(),
            due_date=(self.today + timedelta(days=15)).isoformat(),
        )

        self.assertEqual(response.data["free_copies"], 2)
        self.assertNotIn(
            self.first.id,
            {item["id"] for item in response.data["available_copies"]},
        )

    def test_expired_hold_does_not_block(self):
        make_hold(
            self.book,
            self.first,
            self.other,
            hold_until=timezone.now() - timedelta(hours=1),
        )

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 3)

    def test_own_hold_does_not_block_reader(self):
        make_hold(self.book, self.first, self.reader)

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 3)

    def test_own_hold_blocks_other_reader(self):
        make_hold(self.book, self.first, self.reader)
        self.authenticate(self.other)

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 2)

    def test_hold_on_another_book_is_ignored(self):
        other_book = make_book(title="Другая книга")
        other_copy = make_copy(other_book, "INV-B-001")
        make_hold(other_book, other_copy, self.other)

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 3)

    def test_inactive_copy_is_not_available(self):
        self.third.is_active = False
        self.third.save(update_fields=["is_active"])

        response = self.availability()

        self.assertEqual(response.data["total_copies"], 2)
        self.assertEqual(response.data["free_copies"], 2)
        self.assertNotIn(self.third.id, {item["id"] for item in response.data["copies"]})

    def test_no_copies_means_not_available(self):
        for copy in (self.first, self.second, self.third):
            make_loan(
                copy,
                self.other,
                self.today,
                self.today + timedelta(days=20),
                status=LoanStatus.ACTIVE,
            )

        response = self.availability()

        self.assertEqual(response.data["free_copies"], 0)
        self.assertFalse(response.data["is_available"])
        self.assertEqual(response.data["available_copies"], [])

    def test_copy_states_are_returned(self):
        make_loan(
            self.first,
            self.other,
            self.today,
            self.today + timedelta(days=10),
            status=LoanStatus.ACTIVE,
        )

        response = self.availability(
            start_date=(self.today + timedelta(days=1)).isoformat(),
            due_date=(self.today + timedelta(days=5)).isoformat(),
        )

        states = {
            item["inventory_number"]: item["is_available"]
            for item in response.data["copies"]
        }
        self.assertEqual(
            states,
            {"INV-A-001": False, "INV-A-002": True, "INV-A-003": True},
        )

    def test_start_date_in_past_rejected(self):
        response = self.availability(
            start_date=(self.today - timedelta(days=1)).isoformat()
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")

    def test_due_date_before_start_rejected(self):
        response = self.availability(
            start_date=(self.today + timedelta(days=10)).isoformat(),
            due_date=(self.today + timedelta(days=5)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")

    def test_period_over_thirty_days_rejected(self):
        response = self.availability(
            start_date=self.today.isoformat(),
            due_date=(self.today + timedelta(days=31)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")

    def test_invalid_date_format_returns_validation_error(self):
        response = self.availability(start_date="not-a-date")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("start_date", response.data["fields"])

    def test_inactive_book_is_404_for_reader(self):
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])

        response = self.availability()

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_inactive_book_is_available_to_admin(self):
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])
        self.authenticate(self.admin)

        response = self.availability()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_book_returns_404(self):
        response = self.client.get(f"{BOOKS_URL}999999/availability/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_anonymous_cannot_check_availability(self):
        self.client.credentials()

        response = self.availability()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
