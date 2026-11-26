"""Сериализаторы каталога.

Счётчики доступности проставляет view через `catalog.availability`,
поэтому список не делает запросов на каждую книгу.
"""

from rest_framework import serializers

from catalog.availability import describe
from catalog.models import Book, BookCopy
from reservations.services import queue_position, queue_state
from django.utils import timezone

class BookListSerializer(serializers.ModelSerializer):
    total_copies = serializers.IntegerField(read_only=True)
    free_copies = serializers.IntegerField(read_only=True)

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "author",
            "genre",
            "year",
            "cover_url",
            "is_active",
            "total_copies",
            "free_copies",
        )
        read_only_fields = fields


class BookDetailSerializer(serializers.ModelSerializer):
    total_copies = serializers.SerializerMethodField()
    free_copies = serializers.SerializerMethodField()
    copies = serializers.SerializerMethodField()
    waiting_count = serializers.SerializerMethodField()
    queue_length = serializers.SerializerMethodField()
    my_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "author",
            "genre",
            "year",
            "description",
            "cover_url",
            "is_active",
            "created_at",
            "total_copies",
            "free_copies",
            "copies",
            "waiting_count",
            "queue_length",
            "my_reservation",
        )
        read_only_fields = fields

    def _availability(self, obj):
        if not hasattr(obj, "availability_payload"):
            start, due = self.context["availability_period"]
            obj.availability_payload = describe(
                obj, start, due, self.context.get("reader")
            )
        return obj.availability_payload

    def _queue(self, obj):
        if not hasattr(obj, "queue_payload"):
            obj.queue_payload = queue_state(obj, self.context.get("reader"))
        return obj.queue_payload

    def get_total_copies(self, obj):
        return self._availability(obj)["total_copies"]

    def get_free_copies(self, obj):
        return self._availability(obj)["free_copies"]

    def get_copies(self, obj):
        return self._availability(obj)["copies"]

    def get_waiting_count(self, obj):
        return self._queue(obj)["waiting_count"]

    def get_queue_length(self, obj):
        return self._queue(obj)["queue_length"]

    def get_my_reservation(self, obj):
        reservation = self._queue(obj)["my_reservation"]
        if reservation is None:
            return None
        return {
            "id": reservation.id,
            "status": reservation.status,
            "position": queue_position(reservation),
            "hold_copy_id": reservation.hold_copy_id,
            "hold_until": reservation.hold_until,
        }

MIN_BOOK_YEAR = 1000

class BookWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ("id", "title", "author", "genre", "year", "description", "cover_url", "is_active")

    def validate_year(self, value):
        current_year = timezone.localdate().year
        if value is not None and not MIN_BOOK_YEAR <= value <= current_year:
            raise serializers.ValidationError(
                f"Год должен быть от {MIN_BOOK_YEAR} до {current_year}"
            )
        return value


class BookCopySerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = BookCopy
        fields = ("id", "book_id", "inventory_number", "condition", "is_active")
        read_only_fields = ("id", "book_id")


class AvailabilityQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
