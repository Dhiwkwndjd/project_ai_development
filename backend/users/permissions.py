"""Разрешения по ролям.

Права проверяются только на backend: frontend лишь скрывает разделы.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.models import User


class IsAdmin(BasePermission):
    """Только администратор."""

    message = "Действие доступно только администратору"

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsAdminOrReadOnly(BasePermission):
    """Читать каталог может любой авторизованный, изменять — только администратор."""

    message = "Изменять каталог может только администратор"

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role == User.Role.ADMIN


class IsReader(BasePermission):
    """Только читатель: брони создаёт он, сотрудники работают со статусами."""

    message = "Действие доступно только читателю"

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.READER
        )


class IsLibrarian(BasePermission):
    """Библиотекарь или администратор."""

    message = "Действие доступно только библиотекарю"

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.LIBRARIAN, User.Role.ADMIN)
        )


class IsOwnerOrStaff(BasePermission):
    """Владелец объекта или сотрудник (библиотекарь/администратор).

    Для моделей с полем reader. Имя поля владельца можно переопределить
    атрибутом owner_field у view.
    """

    message = "Нет доступа к чужому объекту"

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role in (User.Role.LIBRARIAN, User.Role.ADMIN):
            return True

        owner_field = getattr(view, "owner_field", "reader")
        owner_id = getattr(obj, f"{owner_field}_id", None)
        return owner_id == user.id
