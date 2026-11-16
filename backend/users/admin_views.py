"""Административное управление пользователями.

Доступ только для роли admin: список, поиск, создание библиотекарей,
смена ролей и блокировка. Права проверяются здесь, не во frontend.
"""

from datetime import datetime, time, timedelta

from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.api import ApiErrorMixin
from users.models import ActivityLog, User
from users.permissions import IsAdmin
from users.serializers import (
    ActivityLogQuerySerializer,
    ActivityLogSerializer,
    AdminUserQuerySerializer,
    AdminUserSerializer,
    LibrarianCreateSerializer,
    UserRoleSerializer,
    UserStatusSerializer,
)


def get_user_or_404(pk):
    user = User.objects.filter(pk=pk).first()
    if user is None:
        raise Http404
    return user


def day_bounds(date_from, date_to):
    """Границы периода как aware datetime (конец не включительно).

    Сравниваем напрямую с datetime: так фильтр не зависит от того, как база
    преобразует дату в строку.
    """
    current = timezone.get_current_timezone()
    start = None
    end = None
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), current)
    if date_to:
        end = timezone.make_aware(
            datetime.combine(date_to + timedelta(days=1), time.min), current
        )
    return start, end


def self_action_response():
    return Response(
        {
            "detail": "Нельзя изменить собственную роль или доступ",
            "code": "self_action",
        },
        status=status.HTTP_409_CONFLICT,
    )


class AdminUserCollectionView(ApiErrorMixin, generics.ListCreateAPIView):
    """`GET` — список и поиск, `POST` — создание библиотекаря."""

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LibrarianCreateSerializer
        return AdminUserSerializer

    def get_queryset(self):
        allowed = ("search", "role", "is_active")
        clean = {
            key: value
            for key, value in self.request.query_params.items()
            if key in allowed and value not in ("", None)
        }
        serializer = AdminUserQuerySerializer(data=clean)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        queryset = User.objects.all().order_by("-created_at", "-id")
        search = filters.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(full_name__icontains=search)
                | Q(phone__icontains=search)
            )
        if filters.get("role"):
            queryset = queryset.filter(role=filters["role"])
        if "is_active" in filters:
            queryset = queryset.filter(is_active=filters["is_active"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            AdminUserSerializer(user).data, status=status.HTTP_201_CREATED
        )


class AdminUserRoleView(ApiErrorMixin, APIView):
    """Смена роли пользователя."""

    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        user = get_user_or_404(pk)
        if user.pk == request.user.pk:
            return self_action_response()

        serializer = UserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.role = serializer.validated_data["role"]
        user.save(update_fields=["role"])
        return Response(AdminUserSerializer(user).data)


class AdminUserStatusView(ApiErrorMixin, APIView):
    """Блокировка (`is_active=false`) и разблокировка пользователя."""

    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        user = get_user_or_404(pk)
        if user.pk == request.user.pk:
            return self_action_response()

        serializer = UserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.is_active = serializer.validated_data["is_active"]
        user.save(update_fields=["is_active"])
        return Response(AdminUserSerializer(user).data)


class ActivityLogListView(ApiErrorMixin, generics.ListAPIView):
    """Журнал действий: только администратор, фильтры и пагинация."""

    permission_classes = [IsAdmin]
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        allowed = ("user_id", "user_email", "action", "date_from", "date_to")
        clean = {
            key: value
            for key, value in self.request.query_params.items()
            if key in allowed and value not in ("", None)
        }
        serializer = ActivityLogQuerySerializer(data=clean)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        queryset = ActivityLog.objects.select_related("user").order_by(
            "-created_at", "-id"
        )
        if filters.get("user_id"):
            queryset = queryset.filter(user_id=filters["user_id"])
        email = filters.get("user_email", "").strip()
        if email:
            queryset = queryset.filter(user__email__icontains=email)
        if filters.get("action"):
            queryset = queryset.filter(action=filters["action"])
        start, end = day_bounds(filters.get("date_from"), filters.get("date_to"))
        if start:
            queryset = queryset.filter(created_at__gte=start)
        if end:
            queryset = queryset.filter(created_at__lt=end)
        return queryset
