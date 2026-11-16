"""Эндпоинты каталога: книги, экземпляры и доступность."""

from django.db.models import ProtectedError, Q
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from catalog.availability import attach_counts, current_period, describe
from catalog.models import Book, BookCopy
from catalog.serializers import (
    AvailabilityQuerySerializer,
    BookCopySerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookWriteSerializer,
)
from loans.services import LoanError, resolve_period
from reservations.serializers import ReservationSerializer
from reservations.services import queue_state
from users.api import ApiErrorMixin
from users.models import ActivityLog, User
from users.permissions import IsAdmin, IsAdminOrReadOnly
from users.services import log_action


def is_admin(user):
    return bool(
        user and user.is_authenticated and user.role == User.Role.ADMIN
    )


def availability_period():
    return current_period()


def parse_availability_period(params):
    """Разобрать `start_date`/`due_date` и проверить их как при брони."""
    clean = {key: value for key, value in params.items() if value not in ("", None)}
    serializer = AvailabilityQuerySerializer(data=clean)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return resolve_period(data.get("start_date"), data.get("due_date"))


class BookViewSet(ApiErrorMixin, viewsets.ModelViewSet):
    """Каталог: чтение всем авторизованным, изменение — администратору."""

    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Book.objects.all()

        if self.action == "list":
            include_inactive = (
                self.request.query_params.get("include_inactive") == "true"
            )
            if not (include_inactive and is_admin(self.request.user)):
                queryset = queryset.filter(is_active=True)
            queryset = self._apply_filters(queryset)
        elif self.action in ("retrieve", "availability"):
            if not is_admin(self.request.user):
                queryset = queryset.filter(is_active=True)
        elif self.action == "genres":
            queryset = queryset.filter(is_active=True)

        return queryset

    def _apply_filters(self, queryset):
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(author__icontains=search)
            )

        genre = self.request.query_params.get("genre", "").strip()
        if genre:
            queryset = queryset.filter(genre__iexact=genre)

        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BookWriteSerializer
        if self.action == "retrieve":
            return BookDetailSerializer
        return BookListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["availability_period"] = availability_period()
        context["reader"] = self.request.user
        return context

    def perform_create(self, serializer):
        book = serializer.save()
        log_action(
            self.request,
            self.request.user,
            ActivityLog.Action.BOOK_CREATED,
            description=f"Книга «{book.title}» добавлена",
            entity=book,
        )

    def perform_update(self, serializer):
        book = serializer.save()
        log_action(
            self.request,
            self.request.user,
            ActivityLog.Action.BOOK_UPDATED,
            description=f"Книга «{book.title}» изменена",
            entity=book,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        books = page if page is not None else list(queryset)
        attach_counts(books, *availability_period(), reader=request.user)
        serializer = self.get_serializer(books, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        book = self.get_object()
        try:
            start, due = parse_availability_period(request.query_params)
        except LoanError as error:
            return Response(
                {"detail": error.detail, "code": error.code},
                status=error.status_code,
            )

        payload = describe(book, start, due, request.user)
        state = queue_state(book, request.user)
        payload.update(
            {
                "book_id": book.id,
                "start_date": start.isoformat(),
                "due_date": due.isoformat(),
                "waiting_count": state["waiting_count"],
                "queue_length": state["queue_length"],
                "my_reservation": (
                    ReservationSerializer(state["my_reservation"]).data
                    if state["my_reservation"]
                    else None
                ),
            }
        )
        return Response(payload)

    @action(detail=False, methods=["get"])
    def genres(self, request):
        genres = (
            Book.objects.filter(is_active=True)
            .order_by("genre")
            .values_list("genre", flat=True)
            .distinct()
        )
        return Response({"genres": list(genres)})

    @action(detail=True, methods=["get", "post"], permission_classes=[IsAdmin])
    def copies(self, request, pk=None):
        book = self.get_object()

        if request.method == "GET":
            serializer = BookCopySerializer(book.copies.all(), many=True)
            return Response(serializer.data)

        serializer = BookCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        copy = serializer.save(book=book)
        log_action(
            request,
            request.user,
            ActivityLog.Action.COPY_CREATED,
            description=(
                f"Экземпляр {copy.inventory_number} добавлен "
                f"для «{book.title}»"
            ),
            entity=copy,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        book = self.get_object()
        book_id = book.id
        title = book.title
        try:
            book.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": "Нельзя удалить книгу с историей броней. "
                    "Снимите её с каталога через is_active.",
                    "code": "book_in_use",
                },
                status=status.HTTP_409_CONFLICT,
            )
        log_action(
            request,
            request.user,
            ActivityLog.Action.BOOK_DELETED,
            description=f"Книга «{title}» удалена",
            entity_type="book",
            entity_id=book_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookCopyDetailView(ApiErrorMixin, generics.RetrieveUpdateDestroyAPIView):
    """Изменение и списание экземпляра: только администратор."""

    permission_classes = [IsAdmin]
    serializer_class = BookCopySerializer

    def get_queryset(self):
        return BookCopy.objects.filter(book_id=self.kwargs["book_id"])

    def perform_update(self, serializer):
        copy = serializer.save()
        log_action(
            self.request,
            self.request.user,
            ActivityLog.Action.COPY_UPDATED,
            description=f"Экземпляр {copy.inventory_number} изменён",
            entity=copy,
        )

    def perform_destroy(self, instance):
        copy_id = instance.id
        number = instance.inventory_number
        title = instance.book.title
        instance.delete()
        log_action(
            self.request,
            self.request.user,
            ActivityLog.Action.COPY_DELETED,
            description=f"Экземпляр {number} списан («{title}»)",
            entity_type="bookcopy",
            entity_id=copy_id,
        )

    def destroy(self, request, *args, **kwargs):
        copy = self.get_object()
        if copy.loans.exists():
            return Response(
                {
                    "detail": "Экземпляр используется в бронях. "
                    "Отметьте его неактивным вместо удаления.",
                    "code": "copy_in_use",
                },
                status=status.HTTP_409_CONFLICT,
            )
        self.perform_destroy(copy)
        return Response(status=status.HTTP_204_NO_CONTENT)
