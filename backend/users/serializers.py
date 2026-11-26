"""Сериализаторы авторизации и пользователя."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.models import ActivityLog, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "role", "is_active")
        read_only_fields = fields

def unique_email_field():
    """Email уникален без учёта регистра: Ivan@x.com и ivan@x.com — один адрес."""
    return serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                lookup="iexact",
                message="Пользователь с таким email уже существует",
            )
        ]
    )

class RegisterSerializer(serializers.ModelSerializer):
    email = unique_email_field()
    password = serializers.CharField(
        write_only=True, validators=[validate_password], style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("id", "email", "password", "full_name", "phone")

    def create(self, validated_data):
        # Роль при регистрации не принимается из запроса: всегда читатель.
        return User.objects.create_user(role=User.Role.READER, **validated_data)


class AdminUserSerializer(serializers.ModelSerializer):
    """Пользователь в админ-панели: все поля, но только для чтения."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class LibrarianCreateSerializer(serializers.ModelSerializer):
    """Создание библиотекаря администратором. Роль задаёт сервер."""

    email = unique_email_field()
    password = serializers.CharField(
        write_only=True, validators=[validate_password], style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("id", "email", "password", "full_name", "phone")

    def create(self, validated_data):
        return User.objects.create_user(
            role=User.Role.LIBRARIAN, **validated_data
        )


class UserRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class UserStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AdminUserQuerySerializer(serializers.Serializer):
    """Поиск и фильтры списка пользователей."""

    search = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)


class ActivityLogSerializer(serializers.ModelSerializer):
    """Запись журнала: кто, что и когда сделал."""

    user = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ActivityLog
        fields = (
            "id",
            "user",
            "action",
            "action_label",
            "entity_type",
            "entity_id",
            "description",
            "ip_address",
            "created_at",
        )
        read_only_fields = fields

    def get_user(self, obj):
        if obj.user is None:
            return None
        return {
            "id": obj.user.id,
            "email": obj.user.email,
            "full_name": obj.user.full_name,
            "role": obj.user.role,
        }


class ActivityLogQuerySerializer(serializers.Serializer):
    """Фильтры журнала: пользователь, действие и период."""

    user_id = serializers.IntegerField(required=False, min_value=1)
    user_email = serializers.CharField(
        required=False, allow_blank=True, max_length=254
    )
    action = serializers.ChoiceField(choices=ActivityLog.Action.choices, required=False)
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


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # В базе email хранится в нижнем регистре.
        attrs["email"] = attrs.get("email", "").strip().lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
