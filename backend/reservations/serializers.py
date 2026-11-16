"""Сериализаторы очереди и удержаний."""

from rest_framework import serializers

from catalog.models import Book
from reservations.models import Reservation
from reservations.services import queue_position


class ReservationCreateSerializer(serializers.Serializer):
    """Запрос на постановку в очередь: только ID книги."""

    book_id = serializers.IntegerField(min_value=1)


class ReservationQuerySerializer(serializers.Serializer):
    """Фильтры списка заявок."""

    book_id = serializers.IntegerField(required=False, min_value=1)
    reader_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.CharField(required=False, allow_blank=True)


class ReservationBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ("id", "title", "author", "year", "cover_url")


class ReservationSerializer(serializers.ModelSerializer):
    book = ReservationBookSerializer(read_only=True)
    reader_id = serializers.IntegerField(read_only=True)
    reader_name = serializers.CharField(source="reader.full_name", read_only=True)
    reader_email = serializers.EmailField(source="reader.email", read_only=True)
    hold_copy_id = serializers.IntegerField(read_only=True)
    position = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id",
            "book",
            "reader_id",
            "reader_name",
            "reader_email",
            "status",
            "position",
            "hold_copy_id",
            "hold_until",
            "created_at",
        )
        read_only_fields = fields

    def get_position(self, obj):
        return queue_position(obj)
