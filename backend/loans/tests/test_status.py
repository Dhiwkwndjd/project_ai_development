"""Смена статуса брони, матрица переходов и права."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.tests.utils import AuthMixin, make_book, make_copy, make_loan, make_user
from loans.models import LoanStatusHistory
from loans.statuses import LoanStatus
from users.models import ActivityLog, User

LOANS_URL = "/api/loans/"


class LoanStatusTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.book = make_book(title="Книга статусов")
        self.copy = make_copy(self.book, "INV-S-001")
        self.second_copy = make_copy(self.book, "INV-S-002")
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)

        self.created_loan = make_loan(
            self.copy,
            self.reader,
            self.today + timedelta(days=1),
            self.today + timedelta(days=10),
        )
        self.active_loan = make_loan(
            self.second_copy,
            self.reader,
            self.today,
            self.today + timedelta(days=10),
            status=LoanStatus.ACTIVE,
        )

    def change_status(self, loan, new_status):
        return self.client.patch(
            f"{LOANS_URL}{loan.id}/status/",
            {"status": new_status},
            format="json",
        )

    def test_librarian_activates_created_loan(self):
        self.authenticate(self.librarian)

        response = self.change_status(self.created_loan, LoanStatus.ACTIVE)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], LoanStatus.ACTIVE)
        self.created_loan.refresh_from_db()
        self.assertEqual(self.created_loan.status, LoanStatus.ACTIVE)
        history = LoanStatusHistory.objects.get(loan=self.created_loan)
        self.assertEqual(history.old_status, LoanStatus.CREATED)
        self.assertEqual(history.new_status, LoanStatus.ACTIVE)
        self.assertEqual(history.changed_by, self.librarian)

    def test_librarian_returns_active_loan(self):
        self.authenticate(self.librarian)

        response = self.change_status(self.active_loan, LoanStatus.RETURNED)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_loan.refresh_from_db()
        self.assertEqual(self.active_loan.status, LoanStatus.RETURNED)

    def test_admin_can_change_status(self):
        self.authenticate(self.admin)

        response = self.change_status(self.created_loan, LoanStatus.ACTIVE)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bad_transition_returns_409(self):
        self.active_loan.status = LoanStatus.RETURNED
        self.active_loan.save(update_fields=["status"])
        self.authenticate(self.librarian)

        response = self.change_status(self.active_loan, LoanStatus.ACTIVE)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "bad_transition")
        self.active_loan.refresh_from_db()
        self.assertEqual(self.active_loan.status, LoanStatus.RETURNED)

    def test_same_status_is_bad_transition(self):
        self.authenticate(self.librarian)

        response = self.change_status(self.created_loan, LoanStatus.CREATED)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "bad_transition")

    def test_reader_cancels_own_created_loan(self):
        self.authenticate(self.reader)

        response = self.change_status(self.created_loan, LoanStatus.CANCELLED)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.created_loan.refresh_from_db()
        self.assertEqual(self.created_loan.status, LoanStatus.CANCELLED)
        history = LoanStatusHistory.objects.get(loan=self.created_loan)
        self.assertEqual(history.changed_by, self.reader)

    def test_librarian_cancels_created_loan(self):
        self.authenticate(self.librarian)

        response = self.change_status(self.created_loan, LoanStatus.CANCELLED)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.created_loan.refresh_from_db()
        self.assertEqual(self.created_loan.status, LoanStatus.CANCELLED)
        history = LoanStatusHistory.objects.get(loan=self.created_loan)
        self.assertEqual(history.changed_by, self.librarian)

    def test_librarian_cannot_cancel_active_loan(self):
        self.authenticate(self.librarian)

        response = self.change_status(self.active_loan, LoanStatus.CANCELLED)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "bad_transition")

    def test_reader_cannot_activate_own_loan(self):
        self.authenticate(self.reader)

        response = self.change_status(self.created_loan, LoanStatus.ACTIVE)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "forbidden")
        self.created_loan.refresh_from_db()
        self.assertEqual(self.created_loan.status, LoanStatus.CREATED)

    def test_reader_cannot_return_own_loan(self):
        self.authenticate(self.reader)

        response = self.change_status(self.active_loan, LoanStatus.RETURNED)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_cannot_change_foreign_loan(self):
        foreign = make_loan(
            self.copy,
            self.other,
            self.today + timedelta(days=20),
            self.today + timedelta(days=25),
        )
        self.authenticate(self.reader)

        response = self.change_status(foreign, LoanStatus.CANCELLED)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_unknown_loan_returns_404(self):
        self.authenticate(self.librarian)

        response = self.client.patch(
            f"{LOANS_URL}999999/status/",
            {"status": LoanStatus.ACTIVE},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_status_returns_400(self):
        self.authenticate(self.librarian)

        response = self.client.patch(
            f"{LOANS_URL}{self.created_loan.id}/status/",
            {"status": "lost"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("status", response.data["fields"])

    def test_status_change_writes_activity_log(self):
        self.authenticate(self.librarian)

        self.change_status(self.created_loan, LoanStatus.ACTIVE)

        log = ActivityLog.objects.get(
            action=ActivityLog.Action.LOAN_STATUS_CHANGED,
            entity_id=self.created_loan.id,
        )
        self.assertEqual(log.user, self.librarian)
        self.assertIn("Создана", log.description)
        self.assertIn("Выдана", log.description)

    def test_anonymous_cannot_change_status(self):
        self.client.credentials()

        response = self.change_status(self.created_loan, LoanStatus.ACTIVE)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LoanListTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.book = make_book(title="Книга списка")
        self.first_copy = make_copy(self.book, "INV-L-001")
        self.second_copy = make_copy(self.book, "INV-L-002")
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)

        self.own_loan = make_loan(
            self.first_copy,
            self.reader,
            self.today,
            self.today + timedelta(days=5),
        )
        self.foreign_loan = make_loan(
            self.second_copy,
            self.other,
            self.today,
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )

    def test_reader_sees_only_own_loans(self):
        self.authenticate(self.reader)

        response = self.client.get(LOANS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.own_loan.id)

    def test_reader_cannot_open_foreign_loan(self):
        self.authenticate(self.reader)

        response = self.client.get(f"{LOANS_URL}{self.foreign_loan.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_librarian_sees_all_loans(self):
        self.authenticate(self.librarian)

        response = self.client.get(LOANS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_admin_sees_all_loans(self):
        self.authenticate(self.admin)

        response = self.client.get(LOANS_URL)

        self.assertEqual(response.data["count"], 2)

    def test_librarian_can_open_foreign_loan(self):
        self.authenticate(self.librarian)

        response = self.client.get(f"{LOANS_URL}{self.foreign_loan.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_status_filter(self):
        self.authenticate(self.librarian)

        response = self.client.get(f"{LOANS_URL}?status=active")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.foreign_loan.id)

    def test_multiple_statuses_filter(self):
        self.authenticate(self.librarian)

        response = self.client.get(f"{LOANS_URL}?status=created,active")

        self.assertEqual(response.data["count"], 2)

    def test_invalid_status_filter_returns_400(self):
        self.authenticate(self.librarian)

        response = self.client.get(f"{LOANS_URL}?status=lost")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_active_on_filter(self):
        self.authenticate(self.librarian)
        date = (self.today + timedelta(days=2)).isoformat()

        response = self.client.get(f"{LOANS_URL}?active_on={date}")

        self.assertEqual(response.data["count"], 2)

    def test_date_range_filter_uses_period_overlap(self):
        inside = make_loan(
            self.first_copy,
            self.other,
            self.today + timedelta(days=10),
            self.today + timedelta(days=15),
        )
        self.authenticate(self.librarian)

        response = self.client.get(
            LOANS_URL,
            {
                "date_from": (self.today + timedelta(days=12)).isoformat(),
                "date_to": (self.today + timedelta(days=13)).isoformat(),
            },
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], inside.id)

    def test_date_range_includes_loan_starting_on_boundary(self):
        self.authenticate(self.librarian)

        response = self.client.get(
            LOANS_URL,
            {
                "date_from": self.today.isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.data["count"], 2)

    def test_invalid_date_range_returns_400(self):
        self.authenticate(self.librarian)

        response = self.client.get(
            LOANS_URL,
            {
                "date_from": (self.today + timedelta(days=5)).isoformat(),
                "date_to": self.today.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_date_range_and_status_filter_work_together(self):
        self.authenticate(self.librarian)

        response = self.client.get(
            LOANS_URL,
            {
                "status": "active",
                "date_from": (self.today + timedelta(days=4)).isoformat(),
                "date_to": (self.today + timedelta(days=6)).isoformat(),
            },
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.foreign_loan.id)

    def test_book_filter(self):
        other_book = make_book(title="Другая книга списка")
        other_copy = make_copy(other_book, "INV-L-003")
        make_loan(
            other_copy,
            self.other,
            self.today,
            self.today + timedelta(days=5),
        )
        self.authenticate(self.librarian)

        response = self.client.get(f"{LOANS_URL}?book_id={self.book.id}")

        self.assertEqual(response.data["count"], 2)

    def test_anonymous_cannot_list_loans(self):
        self.client.credentials()

        response = self.client.get(LOANS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
