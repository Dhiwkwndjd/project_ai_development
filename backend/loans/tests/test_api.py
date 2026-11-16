"""Тесты создания брони и прав доступа."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import Book, BookCopy
from loans.models import Loan, LoanStatusHistory
from loans.statuses import LoanStatus
from reservations.models import Reservation
from users.models import ActivityLog, User

LOANS_URL = "/api/loans/"
PASSWORD = "StrongPass123!"


def make_user(email, role=User.Role.READER):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name="Тестовый Читатель", role=role
    )


def make_book(title="Тестовая книга", is_active=True):
    return Book.objects.create(
        title=title, author="Тестовый Автор", genre="Роман", is_active=is_active
    )


def make_copy(book, number="INV-T-001", is_active=True):
    return BookCopy.objects.create(
        book=book, inventory_number=number, is_active=is_active
    )


def make_loan(copy, reader, start, due, status=LoanStatus.CREATED):
    return Loan.objects.create(
        reader=reader, copy=copy, start_date=start, due_date=due, status=status
    )


class LoanCreateApiTests(APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.book = make_book()
        self.copy = make_copy(self.book)
        self.reader = make_user("reader@test.local")
        self.other_reader = make_user("other@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.authenticate(self.reader)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def post_loan(self, **payload):
        return self.client.post(LOANS_URL, payload, format="json")

    def test_create_loan_defaults_to_14_days(self):
        start = self.today + timedelta(days=1)

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["due_date"], (start + timedelta(days=14)).isoformat())
        self.assertEqual(response.data["status"], LoanStatus.CREATED)
        self.assertEqual(response.data["reader_id"], self.reader.id)
        self.assertEqual(response.data["book"]["title"], self.book.title)

        loan = Loan.objects.get(pk=response.data["id"])
        self.assertEqual(loan.reader, self.reader)
        self.assertEqual(loan.due_date, start + timedelta(days=14))

    def test_create_loan_with_explicit_due_date(self):
        start = self.today
        due = self.today + timedelta(days=10)

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=start.isoformat(),
            due_date=due.isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["due_date"], due.isoformat())

    def test_due_date_can_be_exactly_30_days(self):
        start = self.today + timedelta(days=1)
        due = start + timedelta(days=30)

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=start.isoformat(),
            due_date=due.isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_due_date_over_30_days_rejected(self):
        start = self.today + timedelta(days=1)
        due = start + timedelta(days=31)

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=start.isoformat(),
            due_date=due.isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")
        self.assertFalse(Loan.objects.exists())

    def test_start_date_in_past_rejected(self):
        start = self.today - timedelta(days=1)

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")
        self.assertFalse(Loan.objects.exists())

    def test_due_date_before_start_rejected(self):
        start = self.today + timedelta(days=5)
        due = start - timedelta(days=1)

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=start.isoformat(),
            due_date=due.isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_period")

    def test_overlapping_loan_returns_copy_taken(self):
        start = self.today + timedelta(days=1)
        make_loan(self.copy, self.other_reader, start, start + timedelta(days=10))

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=(start + timedelta(days=5)).isoformat(),
            due_date=(start + timedelta(days=15)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "copy_taken")
        self.assertEqual(Loan.objects.filter(copy=self.copy).count(), 1)

    def test_adjacent_intervals_allowed(self):
        start = self.today + timedelta(days=1)
        first_due = start + timedelta(days=10)
        make_loan(self.copy, self.other_reader, start, first_due)

        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=first_due.isoformat(),
            due_date=(first_due + timedelta(days=10)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cancelled_loan_does_not_block_copy(self):
        start = self.today + timedelta(days=1)
        make_loan(
            self.copy,
            self.other_reader,
            start,
            start + timedelta(days=10),
            status=LoanStatus.CANCELLED,
        )

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_returned_loan_does_not_block_copy(self):
        start = self.today + timedelta(days=1)
        make_loan(
            self.copy,
            self.other_reader,
            start,
            start + timedelta(days=10),
            status=LoanStatus.RETURNED,
        )

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_book_id_picks_free_copy(self):
        second_copy = make_copy(self.book, number="INV-T-002")
        start = self.today + timedelta(days=1)
        make_loan(self.copy, self.other_reader, start, start + timedelta(days=10))

        response = self.post_loan(book_id=self.book.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["copy_id"], second_copy.id)

    def test_no_free_copies_returns_no_copies(self):
        start = self.today + timedelta(days=1)
        make_loan(self.copy, self.other_reader, start, start + timedelta(days=10))

        response = self.post_loan(book_id=self.book.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "no_copies")
        self.assertEqual(Loan.objects.count(), 1)

    def test_inactive_copy_returns_no_copies(self):
        self.copy.is_active = False
        self.copy.save(update_fields=["is_active"])

        response = self.post_loan(copy_id=self.copy.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "no_copies")
        self.assertFalse(Loan.objects.exists())

    def test_inactive_book_returns_no_copies(self):
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])

        response = self.post_loan(book_id=self.book.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "no_copies")

    def test_other_reader_hold_blocks_copy(self):
        start = self.today + timedelta(days=1)
        Reservation.objects.create(
            book=self.book,
            reader=self.other_reader,
            status=Reservation.Status.READY,
            hold_copy=self.copy,
            hold_until=timezone.now() + timedelta(hours=48),
        )

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "copy_taken")

    def test_expired_hold_does_not_block_copy(self):
        start = self.today + timedelta(days=1)
        Reservation.objects.create(
            book=self.book,
            reader=self.other_reader,
            status=Reservation.Status.READY,
            hold_copy=self.copy,
            hold_until=timezone.now() - timedelta(hours=1),
        )

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_own_hold_does_not_block_reader(self):
        start = self.today + timedelta(days=1)
        Reservation.objects.create(
            book=self.book,
            reader=self.reader,
            status=Reservation.Status.READY,
            hold_copy=self.copy,
            hold_until=timezone.now() + timedelta(hours=48),
        )

        response = self.post_loan(copy_id=self.copy.id, start_date=start.isoformat())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_booking_other_copy_releases_hold_to_next(self):
        second_copy = make_copy(self.book, number="INV-T-002")
        hold = Reservation.objects.create(
            book=self.book,
            reader=self.reader,
            status=Reservation.Status.READY,
            hold_copy=self.copy,
            hold_until=timezone.now() + timedelta(hours=48),
        )
        waiting = Reservation.objects.create(
            book=self.book, reader=self.other_reader
        )

        response = self.post_loan(
            copy_id=second_copy.id,
            start_date=(self.today + timedelta(days=1)).isoformat(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["copy_id"], second_copy.id)

        hold.refresh_from_db()
        self.assertEqual(hold.status, Reservation.Status.FULFILLED)
        self.assertIsNone(hold.hold_copy)

        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Reservation.Status.READY)
        self.assertEqual(waiting.hold_copy, self.copy)
        self.assertGreater(waiting.hold_until, timezone.now())

    def test_reader_is_taken_from_jwt_not_from_body(self):
        response = self.post_loan(
            copy_id=self.copy.id,
            reader_id=self.other_reader.id,
            reader=self.other_reader.id,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(pk=response.data["id"])
        self.assertEqual(loan.reader, self.reader)
        self.assertEqual(response.data["reader_id"], self.reader.id)

    def test_creates_history_and_activity_log(self):
        response = self.post_loan(
            copy_id=self.copy.id,
            start_date=(self.today + timedelta(days=1)).isoformat(),
            comment="Нужна для курсовой",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        loan = Loan.objects.get(pk=response.data["id"])
        self.assertEqual(loan.comment, "Нужна для курсовой")

        history = LoanStatusHistory.objects.get(loan=loan)
        self.assertEqual(history.old_status, "")
        self.assertEqual(history.new_status, LoanStatus.CREATED)
        self.assertEqual(history.changed_by, self.reader)

        log = ActivityLog.objects.get(action=ActivityLog.Action.LOAN_CREATED)
        self.assertEqual(log.user, self.reader)
        self.assertEqual(log.entity_type, "loan")
        self.assertEqual(log.entity_id, loan.id)

    def test_book_not_found(self):
        response = self.post_loan(book_id=999999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_copy_not_found(self):
        response = self.post_loan(copy_id=999999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_target_is_required(self):
        response = self.post_loan(start_date=self.today.isoformat())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "target_required")

    def test_invalid_field_format_returns_validation_error(self):
        response = self.post_loan(copy_id="not-a-number")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("copy_id", response.data["fields"])

    def test_anonymous_cannot_create_loan(self):
        self.client.credentials()

        response = self.post_loan(copy_id=self.copy.id)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Loan.objects.exists())

    def test_librarian_cannot_create_loan(self):
        self.authenticate(self.librarian)

        response = self.post_loan(copy_id=self.copy.id)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Loan.objects.exists())
