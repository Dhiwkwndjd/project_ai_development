"""Сериализаторы броней и смены статуса."""

from rest_framework import serializers

from loans.models import Loan
from loans.statuses import LoanStatus


class LoanCreateSerializer(serializers.Serializer):
    """Формат запроса на создание брони. Бизнес-правила — в services."""

    copy_id = serializers.IntegerField(required=False, min_value=1)
    book_id = serializers.IntegerField(required=False, min_value=1)
    start_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    comment = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )


class LoanStatusSerializer(serializers.Serializer):
    """Новый статус брони. Допустимость перехода проверяет services."""

    status = serializers.ChoiceField(choices=LoanStatus.choices)


class LoanQuerySerializer(serializers.Serializer):
    """Фильтры списка броней. Даты задают пересечение с периодом брони."""

    status = serializers.CharField(required=False, allow_blank=True)
    book_id = serializers.IntegerField(required=False, min_value=1)
    reader_id = serializers.IntegerField(required=False, min_value=1)
    active_on = serializers.DateField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "Дата окончания не может быть раньше даты начала"}
            )
        return attrs


class LoanSerializer(serializers.ModelSerializer):
    reader_id = serializers.IntegerField(read_only=True)
    reader = serializers.SerializerMethodField()
    copy_id = serializers.IntegerField(read_only=True)
    copy = serializers.SerializerMethodField()
    book = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = (
            "id",
            "reader_id",
            "reader",
            "copy_id",
            "copy",
            "book",
            "start_date",
            "due_date",
            "status",
            "comment",
            "created_at",
        )
        read_only_fields = fields

    def get_reader(self, obj):
        reader = obj.reader
        return {"id": reader.id, "full_name": reader.full_name, "email": reader.email}

    def get_copy(self, obj):
        return {
            "id": obj.copy_id,
            "inventory_number": obj.copy.inventory_number,
        }

    def get_book(self, obj):
        book = obj.copy.book
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "cover_url": book.cover_url,
        }
