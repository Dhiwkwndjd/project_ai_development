"""Эндпоинты авторизации."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.api import ApiErrorMixin
from users.models import ActivityLog, User
from users.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from users.services import log_action


class RegisterView(ApiErrorMixin, APIView):
    """Регистрация читателя. Роль всегда reader."""

    permission_classes = [AllowAny]
    # Просроченный access в заголовке не должен мешать регистрации.
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_action(
            request,
            user,
            ActivityLog.Action.REGISTER,
            description="Регистрация читателя",
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(ApiErrorMixin, TokenObtainPairView):
    """Вход по email и паролю. Возвращает токены и данные пользователя."""

    permission_classes = [AllowAny]
    # Старый access в заголовке не должен превращать вход в 401.
    authentication_classes = []
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            user_id = response.data["user"]["id"]
            user = User.objects.filter(pk=user_id).first()
            if user:
                log_action(
                    request, user, ActivityLog.Action.LOGIN, description="Вход в систему"
                )
        return response


class RefreshView(ApiErrorMixin, TokenRefreshView):
    """Обновление access-токена по refresh-токену."""

    permission_classes = [AllowAny]
    # Refresh авторизуется самим refresh-токеном, а не заголовком.
    authentication_classes = []


class LogoutView(ApiErrorMixin, APIView):
    """Выход: refresh-токен попадает в blacklist."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_token = request.data.get("refresh")
        if not raw_token:
            return Response(
                {"detail": "Передайте refresh-токен", "code": "refresh_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(raw_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Недействительный refresh-токен", "code": "invalid_refresh"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_action(
            request, request.user, ActivityLog.Action.LOGOUT, description="Выход из системы"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(ApiErrorMixin, APIView):
    """Текущий пользователь."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
