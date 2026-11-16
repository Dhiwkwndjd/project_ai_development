"""Список каталога: поиск, фильтр, пагинация, счётчики."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.tests.utils import (
    AuthMixin,
    find_book,
    make_book,
    make_copy,
    make_hold,
    make_loan,
    make_user,
)
from loans.statuses import LoanStatus

BOOKS_URL = "/api/books/"


class CatalogListTests(AuthMixin, APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.reader = make_user("reader@test.local")
        self.other = make_user("other@test.local")
        self.authenticate(self.reader)

    def get_list(self, **params):
        return self.client.get(BOOKS_URL, params)

    def test_anonymous_cannot_read_catalog(self):
        self.client.credentials()

        response = self.get_list()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "unauthorized")

    def test_search_by_title(self):
        book = make_book(title="Мастер и Маргарита", author="Михаил Булгаков")
        make_book(title="1984", author="Джордж Оруэлл", genre="Антиутопия")

        response = self.get_list(search="Маргарита")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], book.id)

    def test_search_by_author(self):
        book = make_book(title="Солярис", author="Станислав Лем", genre="Фантастика")
        make_book(title="1984", author="Джордж Оруэлл", genre="Антиутопия")

        response = self.get_list(search="Лем")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], book.id)

    def test_search_without_matches_returns_empty_page(self):
        make_book(title="Мастер и Маргарита")

        response = self.get_list(search="нет такой книги")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_genre_filter(self):
        novel = make_book(title="Анна Каренина", genre="Роман")
        make_book(title="Солярис", genre="Фантастика")

        response = self.get_list(genre="Роман")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], novel.id)

    def test_search_and_genre_work_together(self):
        make_book(title="Мастер и Маргарита", genre="Роман")

        response = self.get_list(search="Мастер", genre="Фантастика")

        self.assertEqual(response.data["count"], 0)

    def test_inactive_books_are_hidden(self):
        active = make_book(title="Видимая книга")
        make_book(title="Скрытая книга", is_active=False)

        response = self.get_list()

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], active.id)

    def test_pagination_uses_page_size_nine(self):
        for index in range(10):
            make_book(title=f"Книга {index:02d}", author=f"Автор {index:02d}")
        make_book(title="Неактивная", is_active=False)

        first = self.get_list(page=1)
        second = self.get_list(page=2)

        self.assertEqual(first.data["count"], 10)
        self.assertEqual(len(first.data["results"]), 9)
        self.assertIsNotNone(first.data["next"])
        self.assertEqual(len(second.data["results"]), 1)
        self.assertIsNotNone(second.data["previous"])

    def test_list_shows_total_and_free_copies(self):
        book = make_book(title="Книга с экземплярами")
        first = make_copy(book, "INV-001")
        second = make_copy(book, "INV-002")
        third = make_copy(book, "INV-003")
        make_copy(book, "INV-004")

        make_loan(
            first,
            self.other,
            self.today - timedelta(days=1),
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )
        make_loan(
            second,
            self.other,
            self.today - timedelta(days=1),
            self.today + timedelta(days=5),
            status=LoanStatus.RETURNED,
        )
        make_loan(
            third,
            self.other,
            self.today + timedelta(days=5),
            self.today + timedelta(days=15),
            status=LoanStatus.CREATED,
        )

        response = self.get_list()
        item = find_book(response.data["results"], book.id)

        self.assertEqual(item["total_copies"], 4)
        self.assertEqual(item["free_copies"], 3)

    def test_inactive_copies_are_not_counted(self):
        book = make_book(title="Книга со списанным экземпляром")
        make_copy(book, "INV-001")
        make_copy(book, "INV-002", is_active=False)

        response = self.get_list()
        item = find_book(response.data["results"], book.id)

        self.assertEqual(item["total_copies"], 1)
        self.assertEqual(item["free_copies"], 1)

    def test_active_hold_reduces_free_copies(self):
        book = make_book(title="Книга с удержанием")
        held = make_copy(book, "INV-001")
        make_copy(book, "INV-002")
        make_hold(book, held, self.other)

        response = self.get_list()
        item = find_book(response.data["results"], book.id)

        self.assertEqual(item["total_copies"], 2)
        self.assertEqual(item["free_copies"], 1)

    def test_own_hold_does_not_hide_copy_from_reader(self):
        book = make_book(title="Моя книга")
        held = make_copy(book, "INV-001")
        make_hold(book, held, self.reader)

        response = self.get_list()
        item = find_book(response.data["results"], book.id)

        self.assertEqual(item["free_copies"], 1)

    def test_list_returns_published_year(self):
        book = make_book(title="Книга с годом издания")
        book.year = 1967
        book.save(update_fields=["year"])

        response = self.get_list()

        item = find_book(response.data["results"], book.id)
        self.assertEqual(item["year"], 1967)

    def test_detail_contains_description_and_copy_states(self):
        book = make_book(title="Подробная книга")
        busy = make_copy(book, "INV-001")
        make_copy(book, "INV-002")
        make_loan(
            busy,
            self.other,
            self.today,
            self.today + timedelta(days=5),
            status=LoanStatus.ACTIVE,
        )

        response = self.client.get(f"{BOOKS_URL}{book.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], book.title)
        self.assertEqual(response.data["total_copies"], 2)
        self.assertEqual(response.data["free_copies"], 1)
        states = {copy["inventory_number"]: copy["is_available"] for copy in response.data["copies"]}
        self.assertEqual(states, {"INV-001": False, "INV-002": True})

    def test_genres_are_unique_and_only_active(self):
        make_book(title="Роман 1", genre="Роман")
        make_book(title="Роман 2", genre="Роман")
        make_book(title="Поэзия", genre="Поэзия")
        make_book(title="Скрытый детектив", genre="Детектив", is_active=False)

        response = self.client.get(f"{BOOKS_URL}genres/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["genres"], ["Поэзия", "Роман"])
