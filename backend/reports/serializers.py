"""Валидация параметров отчётов."""

from rest_framework import serializers


class PeriodQuerySerializer(serializers.Serializer):
    """Необязательный период отчёта: даты в формате ISO 8601."""

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
