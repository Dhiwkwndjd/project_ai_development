"""Админка каталога."""

from django.contrib import admin

from catalog.models import Book, BookCopy


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 0
    fields = ("inventory_number", "condition", "is_active")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "genre", "year", "is_active")
    list_filter = ("genre", "is_active")
    search_fields = ("title", "author")
    inlines = [BookCopyInline]


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("inventory_number", "book", "condition", "is_active")
    list_filter = ("condition", "is_active")
    search_fields = ("inventory_number", "book__title")
