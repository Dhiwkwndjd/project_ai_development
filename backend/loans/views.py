"""Эндпоинты броней: создание, списки, смена статуса."""

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from loans.models import Loan
from loans.serializers import (
    LoanCreateSerializer,
    LoanQuerySerializer,
    LoanSerializer,
    LoanStatusSerializer,
)
from loans.services import LoanError, change_loan_status, create_loan
from loans.statuses import LoanStatus
from users.api import ApiErrorMixin
from users.models import User
from users.permissions import IsReader


def scoped_loans(user):
    """Читатель видит только свои брони, сотрудники — все."""
    queryset = Loan.objects.select_related("reader", "copy__book")
    if user.role == User.Role.READER:
        return queryset.filter(reader=user)
    return queryset


def parse_filters(request):
    """Проверить параметры списка; статус допускает несколько через запятую."""
    allowed = ("status", "book_id", "reader_id", "active_on", "date_from", "date_to")
    clean = {
        key: value
        for key, value in request.query_params.items()
        if key in allowed and value not in ("", None)
    }
    serializer = LoanQuerySerializer(data=clean)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    statuses = []
    raw_statuses = data.get("status")
    if raw_statuses:
        statuses = [item.strip() for item in raw_statuses.split(",") if item.strip()]
        invalid = [item for item in statuses if item not in LoanStatus.values]
        if invalid:
            raise ValidationError(
                {"status": f"Неизвестный статус: {', '.join(invalid)}"}
            )

    return {
        "statuses": statuses,
        "book_id": data.get("book_id"),
        "reader_id": data.get("reader_id"),
        "active_on": data.get("active_on"),
        "date_from": data.get("date_from"),
        "date_to": data.get("date_to"),
    }


def apply_filters(queryset, filters):
    if filters["statuses"]:
        queryset = queryset.filter(status__in=filters["statuses"])
    if filters["book_id"]:
        queryset = queryset.filter(copy__book_id=filters["book_id"])
    if filters["reader_id"]:
        queryset = queryset.filter(reader_id=filters["reader_id"])
    if filters["active_on"]:
        date = filters["active_on"]
        queryset = queryset.filter(start_date__lte=date, due_date__gt=date)
    # Пересечение периода брони с выбранным диапазоном дат.
    if filters["date_from"]:
        queryset = queryset.filter(due_date__gt=filters["date_from"])
    if filters["date_to"]:
        queryset = queryset.filter(start_date__lte=filters["date_to"])
    return queryset


class LoanCollectionView(ApiErrorMixin, generics.ListAPIView):
    """`GET` — список броней, `POST` — создание брони читателем."""

    serializer_class = LoanSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsReader()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = scoped_loans(self.request.user)
        queryset = apply_filters(queryset, parse_filters(self.request))
        return queryset.order_by("-created_at", "-id")

    def post(self, request):
        serializer = LoanCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "detail": "Проверьте параметры запроса",
                    "code": "validation_error",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        if not data.get("copy_id") and not data.get("book_id"):
            return Response(
                {"detail": "Укажите экземпляр или книгу", "code": "target_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            loan = create_loan(
                reader=request.user,
                copy_id=data.get("copy_id"),
                book_id=data.get("book_id"),
                start_date=data.get("start_date"),
                due_date=data.get("due_date"),
                comment=data.get("comment", ""),
                request=request,
            )
        except LoanError as error:
            return Response(
                {"detail": error.detail, "code": error.code},
                status=error.status_code,
            )

        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)


class LoanDetailView(ApiErrorMixin, generics.RetrieveAPIView):
    """Одна бронь: своя для читателя, любая для сотрудника."""

    permission_classes = [IsAuthenticated]
    serializer_class = LoanSerializer

    def get_queryset(self):
        return scoped_loans(self.request.user)


class LoanStatusView(ApiErrorMixin, APIView):
    """Смена статуса по матрице переходов из `loans/statuses.py`."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = LoanStatusSerializer(data=request.data)
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
            loan = change_loan_status(
                loan_id=pk,
                new_status=serializer.validated_data["status"],
                actor=request.user,
                request=request,
            )
        except LoanError as error:
            return Response(
                {"detail": error.detail, "code": error.code},
                status=error.status_code,
            )

        return Response(LoanSerializer(loan).data)
