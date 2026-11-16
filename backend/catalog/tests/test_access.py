"""Права доступа и CRUD каталога."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Book, BookCopy
from catalog.tests.utils import (
    AuthMixin,
    make_book,
    make_copy,
    make_loan,
    make_user,
)
from loans.statuses import LoanStatus
from users.models import ActivityLog, User

BOOKS_URL = "/api/books/"


class CatalogPermissionTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.reader = make_user("reader@test.local")
        self.librarian = make_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)
        self.book = make_book(title="Открытая книга")
        self.hidden = make_book(title="Скрытая книга", is_active=False)

    def test_reader_sees_only_active_books(self):
        self.authenticate(self.reader)

        response = self.client.get(BOOKS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_can_request_inactive_books(self):
        self.authenticate(self.admin)

        response = self.client.get(BOOKS_URL, {"include_inactive": "true"})

        self.assertEqual(response.data["count"], 2)

    def test_admin_without_flag_still_sees_only_active(self):
        self.authenticate(self.admin)

        response = self.client.get(BOOKS_URL)

        self.assertEqual(response.data["count"], 1)

    def test_inactive_book_detail_is_404_for_reader(self):
        self.authenticate(self.reader)

        response = self.client.get(f"{BOOKS_URL}{self.hidden.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_inactive_book_detail_is_available_to_admin(self):
        self.authenticate(self.admin)

        response = self.client.get(f"{BOOKS_URL}{self.hidden.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.hidden.id)

    def test_unknown_book_returns_not_found(self):
        self.authenticate(self.reader)

        response = self.client.get(f"{BOOKS_URL}999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")

    def test_reader_cannot_create_book(self):
        self.authenticate(self.reader)

        response = self.client.post(
            BOOKS_URL,
            {"title": "Новая", "author": "Автор", "genre": "Роман"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "forbidden")
        self.assertFalse(Book.objects.filter(title="Новая").exists())

    def test_librarian_cannot_create_book(self):
        self.authenticate(self.librarian)

        response = self.client.post(
            BOOKS_URL,
            {"title": "Новая", "author": "Автор", "genre": "Роман"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_book(self):
        self.authenticate(self.admin)

        response = self.client.post(
            BOOKS_URL,
            {
                "title": "Новая книга",
                "author": "Новый автор",
                "genre": "Роман",
                "year": 2001,
                "description": "Описание",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Book.objects.get(title="Новая книга").year, 2001)

    def test_admin_invalid_year_is_validation_error(self):
        self.authenticate(self.admin)

        response = self.client.post(
            BOOKS_URL,
            {"title": "Книга", "author": "Автор", "genre": "Роман", "year": "не год"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("year", response.data["fields"])

    def test_admin_validation_error_has_code_and_fields(self):
        self.authenticate(self.admin)

        response = self.client.post(
            BOOKS_URL, {"title": "", "author": "", "genre": ""}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("title", response.data["fields"])

    def test_admin_updates_book(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{BOOKS_URL}{self.book.id}/", {"is_active": False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertFalse(self.book.is_active)

    def test_admin_book_create_update_delete_are_logged(self):
        self.authenticate(self.admin)

        created = self.client.post(
            BOOKS_URL,
            {"title": "Книга журнала", "author": "Автор", "genre": "Роман"},
            format="json",
        )
        book_id = created.data["id"]
        self.client.patch(
            f"{BOOKS_URL}{book_id}/", {"title": "Книга журнала 2"}, format="json"
        )
        self.client.delete(f"{BOOKS_URL}{book_id}/")

        actions = list(
            ActivityLog.objects.filter(
                entity_type="book", entity_id=book_id
            )
            .order_by("created_at", "id")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [
                ActivityLog.Action.BOOK_CREATED,
                ActivityLog.Action.BOOK_UPDATED,
                ActivityLog.Action.BOOK_DELETED,
            ],
        )

    def test_reader_cannot_update_book(self):
        self.authenticate(self.reader)

        response = self.client.patch(
            f"{BOOKS_URL}{self.book.id}/", {"title": "Подмена"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.book.refresh_from_db()
        self.assertNotEqual(self.book.title, "Подмена")

    def test_admin_deletes_empty_book(self):
        self.authenticate(self.admin)

        response = self.client.delete(f"{BOOKS_URL}{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(pk=self.book.id).exists())

    def test_admin_cannot_delete_book_with_loan_history(self):
        copy = make_copy(self.book, "INV-DEL-001")
        make_loan(
            copy,
            self.reader,
            self.today,
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )
        self.authenticate(self.admin)

        response = self.client.delete(f"{BOOKS_URL}{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "book_in_use")
        self.assertTrue(Book.objects.filter(pk=self.book.id).exists())


class BookCopyApiTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.reader = make_user("reader@test.local")
        self.admin = make_user("admin@test.local", role=User.Role.ADMIN)
        self.book = make_book(title="Книга с экземплярами")
        self.copy = make_copy(self.book, "INV-001")
        self.copies_url = f"{BOOKS_URL}{self.book.id}/copies/"

    def test_reader_cannot_list_copies(self):
        self.authenticate(self.reader)

        response = self.client.get(self.copies_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_copies(self):
        self.authenticate(self.admin)

        response = self.client.get(self.copies_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["inventory_number"], "INV-001")

    def test_admin_adds_copy(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.copies_url,
            {"inventory_number": "INV-002", "condition": "new"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["book_id"], self.book.id)
        self.assertTrue(BookCopy.objects.filter(inventory_number="INV-002").exists())

    def test_duplicate_inventory_number_is_validation_error(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.copies_url, {"inventory_number": "INV-001"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("inventory_number", response.data["fields"])

    def test_admin_copy_create_update_delete_are_logged(self):
        self.authenticate(self.admin)

        created = self.client.post(
            self.copies_url,
            {"inventory_number": "INV-LOG-001", "condition": "new"},
            format="json",
        )
        copy_id = created.data["id"]
        copy_url = f"{self.copies_url}{copy_id}/"
        self.client.patch(copy_url, {"condition": "worn"}, format="json")
        self.client.delete(copy_url)

        actions = list(
            ActivityLog.objects.filter(
                entity_type="bookcopy", entity_id=copy_id
            )
            .order_by("created_at", "id")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [
                ActivityLog.Action.COPY_CREATED,
                ActivityLog.Action.COPY_UPDATED,
                ActivityLog.Action.COPY_DELETED,
            ],
        )

    def test_reader_cannot_change_copy(self):
        self.authenticate(self.reader)

        response = self.client.patch(
            f"{self.copies_url}{self.copy.id}/", {"condition": "worn"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.condition, BookCopy.Condition.GOOD)

    def test_admin_changes_copy(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{self.copies_url}{self.copy.id}/", {"condition": "worn"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.condition, BookCopy.Condition.WORN)

    def test_admin_deletes_copy_without_history(self):
        self.authenticate(self.admin)

        response = self.client.delete(f"{self.copies_url}{self.copy.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BookCopy.objects.filter(pk=self.copy.id).exists())

    def test_admin_cannot_delete_copy_with_loan_history(self):
        make_loan(
            self.copy,
            self.reader,
            self.today,
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )
        self.authenticate(self.admin)

        response = self.client.delete(f"{self.copies_url}{self.copy.id}/")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "copy_in_use")
        self.assertTrue(BookCopy.objects.filter(pk=self.copy.id).exists())

    def test_anonymous_cannot_read_copies(self):
        response = self.client.get(self.copies_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
