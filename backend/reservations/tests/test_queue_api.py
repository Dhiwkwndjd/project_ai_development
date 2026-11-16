"""Очередь: постановка, FIFO-позиция, дубли и права."""

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.tests.utils import AuthMixin, make_book, make_copy, make_hold, make_user
from reservations.models import Reservation
from users.models import User

RESERVATIONS_URL = "/api/reservations/"
MY_URL = "/api/reservations/my/"


class ReservationCreateTests(AuthMixin, APITestCase):
    def setUp(self):
        self.book = make_book(title="Книга очереди")
        self.copy = make_copy(self.book)
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)
        self.authenticate(self.reader)

    def join(self, book_id=None):
        return self.client.post(
            RESERVATIONS_URL,
            {"book_id": book_id or self.book.id},
            format="json",
        )

    def test_first_waiting_has_position_one(self):
        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Reservation.Status.WAITING)
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(response.data["reader_id"], self.reader.id)
        self.assertEqual(response.data["book"]["id"], self.book.id)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_queue_is_fifo(self):
        self.join()
        self.authenticate(self.other)

        response = self.join()

        self.assertEqual(response.data["position"], 2)
        self.assertEqual(
            list(
                Reservation.objects.order_by("created_at", "id").values_list(
                    "reader__email", flat=True
                )
            ),
            ["reader@test.local", "other@test.local"],
        )

    def test_duplicate_active_reservation_returns_409(self):
        self.join()

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "already_queued")
        self.assertEqual(Reservation.objects.count(), 1)

    def test_ready_reservation_also_blocks_duplicate(self):
        make_hold(self.book, self.copy, self.reader)

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "already_queued")

    def test_cancelled_reservation_allows_new_one(self):
        first = self.join()
        self.client.delete(f"{RESERVATIONS_URL}{first.data['id']}/")

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reservation.objects.count(), 2)

    def test_unknown_book_returns_404(self):
        response = self.join(book_id=999999)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_inactive_book_returns_404(self):
        self.book.is_active = False
        self.book.save(update_fields=["is_active"])

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_anonymous_cannot_join_queue(self):
        self.client.credentials()

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Reservation.objects.exists())

    def test_librarian_cannot_join_queue(self):
        self.authenticate(self.librarian)

        response = self.join()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Reservation.objects.exists())

    def test_reader_cannot_use_staff_list(self):
        response = self.client.get(RESERVATIONS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_sees_all_reservations(self):
        self.join()
        self.authenticate(self.other)
        self.join()

        self.authenticate(self.librarian)
        response = self.client.get(RESERVATIONS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_admin_sees_all_reservations(self):
        self.join()
        self.authenticate(self.admin)

        response = self.client.get(RESERVATIONS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class ReservationMyListTests(AuthMixin, APITestCase):
    def setUp(self):
        self.book = make_book(title="Книга моей очереди")
        self.copy = make_copy(self.book)
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.authenticate(self.reader)

    def test_my_list_returns_only_own_reservations(self):
        Reservation.objects.create(book=self.book, reader=self.reader)
        Reservation.objects.create(book=self.book, reader=self.other)

        response = self.client.get(MY_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["reader_id"], self.reader.id)

    def test_my_list_requires_reader(self):
        self.authenticate(make_user("librarian@test.local", role=User.Role.LIBRARIAN))

        response = self.client.get(MY_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ReservationCancelTests(AuthMixin, APITestCase):
    def setUp(self):
        self.book = make_book(title="Книга отмены")
        self.copy = make_copy(self.book)
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)
        self.authenticate(self.reader)

    def cancel(self, reservation_id):
        return self.client.delete(f"{RESERVATIONS_URL}{reservation_id}/")

    def test_owner_cancels_waiting_reservation(self):
        reservation = Reservation.objects.create(book=self.book, reader=self.reader)

        response = self.cancel(reservation.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

    def test_reader_cannot_cancel_foreign_reservation(self):
        reservation = Reservation.objects.create(book=self.book, reader=self.other)

        response = self.cancel(reservation.id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.WAITING)

    def test_admin_cancels_foreign_reservation(self):
        reservation = Reservation.objects.create(book=self.book, reader=self.other)
        self.authenticate(self.admin)

        response = self.cancel(reservation.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cancel_ready_hold_gives_copy_to_next(self):
        first = make_hold(self.book, self.copy, self.reader)
        second = Reservation.objects.create(book=self.book, reader=self.other)

        response = self.cancel(first.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        second.refresh_from_db()
        self.assertEqual(second.status, Reservation.Status.READY)
        self.assertEqual(second.hold_copy, self.copy)
        self.assertIsNotNone(second.hold_until)

    def test_cannot_cancel_terminal_reservation(self):
        reservation = Reservation.objects.create(
            book=self.book,
            reader=self.reader,
            status=Reservation.Status.CANCELLED,
        )

        response = self.cancel(reservation.id)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "bad_transition")

    def test_anonymous_cannot_cancel(self):
        reservation = Reservation.objects.create(book=self.book, reader=self.reader)
        self.client.credentials()

        response = self.cancel(reservation.id)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
