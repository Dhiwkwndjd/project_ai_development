"""Модели каталога: книги и их физические экземпляры."""

from django.db import models


class Book(models.Model):
    """Книга в каталоге библиотеки."""

    title = models.CharField("Название", max_length=200)
    author = models.CharField("Автор", max_length=150)
    genre = models.CharField("Жанр", max_length=80)
    year = models.PositiveSmallIntegerField("Год издания", null=True, blank=True)
    description = models.TextField("Описание", blank=True)
    cover_url = models.URLField("Обложка (URL)", blank=True)
    is_active = models.BooleanField("В каталоге", default=True)
    created_at = models.DateTimeField("Добавлена", auto_now_add=True)

    class Meta:
        db_table = "books"
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["title"]
        indexes = [
            models.Index(fields=["title"], name="books_title_idx"),
            models.Index(fields=["genre"], name="books_genre_idx"),
        ]

    def __str__(self):
        return f"{self.title} — {self.author}"


class BookCopy(models.Model):
    """Физический экземпляр книги."""

    class Condition(models.TextChoices):
        NEW = "new", "Новый"
        GOOD = "good", "Хороший"
        WORN = "worn", "Потрёпанный"

    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="copies", verbose_name="Книга"
    )
    inventory_number = models.CharField(
        "Инвентарный номер", max_length=30, unique=True
    )
    condition = models.CharField(
        "Состояние", max_length=10, choices=Condition.choices, default=Condition.GOOD
    )
    is_active = models.BooleanField("Доступен", default=True)

    class Meta:
        db_table = "book_copies"
        verbose_name = "Экземпляр книги"
        verbose_name_plural = "Экземпляры книг"
        ordering = ["inventory_number"]
        indexes = [
            models.Index(fields=["book", "is_active"], name="copies_book_active_idx"),
        ]

    def __str__(self):
        return f"{self.inventory_number}: {self.book.title}"
