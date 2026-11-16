"""Общий формат ошибок API.

Все эндпоинты отвечают `{"detail": "...", "code": "..."}`. Миксин
перехватывает стандартные исключения DRF и Django, чтобы код ответа
и тело были одинаковыми во всех приложениях.
"""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response


class ApiErrorMixin:
    """Единый формат ошибок для классов DRF."""

    @staticmethod
    def _unauthorized_response(message, code):
        response = Response(
            {"detail": message, "code": code},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        response["WWW-Authenticate"] = 'Bearer realm="api"'
        return response

    def handle_exception(self, exc):
        if isinstance(exc, ValidationError):
            return Response(
                {
                    "detail": "Проверьте параметры запроса",
                    "code": "validation_error",
                    "fields": exc.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, PermissionDenied):
            return Response(
                {"detail": str(exc.detail), "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if isinstance(exc, NotAuthenticated):
            return self._unauthorized_response("Требуется авторизация", "unauthorized")
        if isinstance(exc, AuthenticationFailed):
            # SimpleJWT кладёт detail/code словарём, DRF — строкой с кодом.
            detail = exc.detail
            if isinstance(detail, dict):
                message = detail.get("detail") or "Требуется авторизация"
                code = detail.get("code") or "unauthorized"
            else:
                message = str(detail) or "Требуется авторизация"
                code = getattr(detail, "code", None) or "unauthorized"
            return self._unauthorized_response(message, code)
        if isinstance(exc, (Http404, NotFound)):
            return Response(
                {"detail": "Объект не найден", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return super().handle_exception(exc)
