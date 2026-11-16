"""Эндпоинты очереди: постановка, мои заявки, список и отмена."""

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reservations.models import Reservation
from reservations.serializers import (
    ReservationCreateSerializer,
    ReservationQuerySerializer,
    ReservationSerializer,
)
from reservations.services import (
    ReservationError,
    cancel_reservation,
    create_reservation,
    expire_all_outdated_holds,
    expire_reader_holds,
)
from users.api import ApiErrorMixin
from users.permissions import IsLibrarian, IsReader


def parse_filters(request):
    """Разобрать фильтры; статус допускает несколько значений через запятую."""
    allowed = ("book_id", "reader_id", "status")
    clean = {
        key: value
        for key, value in request.query_params.items()
        if key in allowed and value not in ("", None)
    }
    serializer = ReservationQuerySerializer(data=clean)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    statuses = []
    raw_statuses = data.get("status")
    if raw_statuses:
        statuses = [item.strip() for item in raw_statuses.split(",") if item.strip()]
        invalid = [item for item in statuses if item not in Reservation.Status.values]
        if invalid:
            raise ValidationError(
                {"status": f"Неизвестный статус: {', '.join(invalid)}"}
            )

    return {
        "book_id": data.get("book_id"),
        "reader_id": data.get("reader_id"),
        "statuses": statuses,
    }


def apply_filters(queryset, filters):
    if filters["book_id"]:
        queryset = queryset.filter(book_id=filters["book_id"])
    if filters["reader_id"]:
        queryset = queryset.filter(reader_id=filters["reader_id"])
    if filters["statuses"]:
        queryset = queryset.filter(status__in=filters["statuses"])
    return queryset


class ReservationCollectionView(ApiErrorMixin, generics.ListAPIView):
    """`POST` — читатель встаёт в очередь, `GET` — сотрудник видит всё."""

    serializer_class = ReservationSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsReader()]
        return [IsLibrarian()]

    def get_queryset(self):
        expire_all_outdated_holds()
        queryset = Reservation.objects.select_related(
            "book", "reader", "hold_copy"
        )
        queryset = apply_filters(queryset, parse_filters(self.request))
        return queryset.order_by("book__title", "created_at", "id")

    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "detail": "Проверьте параметры запроса",
                    "code": "validation_error",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reservation = create_reservation(
                reader=request.user,
                book_id=serializer.validated_data["book_id"],
                request=request,
            )
        except ReservationError as error:
            return Response(
                {"detail": error.detail, "code": error.code},
                status=error.status_code,
            )

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class ReservationMyListView(ApiErrorMixin, generics.ListAPIView):
    """Мои заявки и позиция в очереди."""

    permission_classes = [IsReader]
    serializer_class = ReservationSerializer

    def get_queryset(self):
        expire_reader_holds(self.request.user)
        queryset = Reservation.objects.filter(
            reader=self.request.user
        ).select_related("book", "reader", "hold_copy")
        queryset = apply_filters(queryset, parse_filters(self.request))
        return queryset.order_by("created_at", "id")


class ReservationCancelView(ApiErrorMixin, APIView):
    """Отмена заявки владельцем или администратором."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            cancel_reservation(pk, request.user, request=request)
        except ReservationError as error:
            return Response(
                {"detail": error.detail, "code": error.code},
                status=error.status_code,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
