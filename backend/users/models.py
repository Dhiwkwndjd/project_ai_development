"""Пользователь библиотеки и роли."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """Менеджер пользователей, где логин — email."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email).lower()        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields["role"] != User.Role.ADMIN:
            raise ValueError("Суперпользователь должен иметь роль admin")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Пользователь системы: читатель, библиотекарь или администратор."""

    class Role(models.TextChoices):
        READER = "reader", "Читатель"
        LIBRARIAN = "librarian", "Библиотекарь"
        ADMIN = "admin", "Администратор"

    email = models.EmailField("Email", unique=True)
    full_name = models.CharField("ФИО", max_length=150)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    role = models.CharField(
        "Роль", max_length=20, choices=Role.choices, default=Role.READER
    )
    is_active = models.BooleanField("Активен", default=True)
    is_staff = models.BooleanField("Доступ в админку", default=False)
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_librarian(self):
        return self.role in (self.Role.LIBRARIAN, self.Role.ADMIN)


class ActivityLog(models.Model):
    """Журнал действий пользователей."""

    class Action(models.TextChoices):
        REGISTER = "register", "Регистрация"
        LOGIN = "login", "Вход"
        LOGOUT = "logout", "Выход"
        LOAN_CREATED = "loan_created", "Создание брони"
        LOAN_STATUS_CHANGED = "loan_status_changed", "Смена статуса брони"
        RESERVATION_CREATED = "reservation_created", "Постановка в очередь"
        RESERVATION_READY = "reservation_ready", "Удержание экземпляра"
        RESERVATION_FULFILLED = "reservation_fulfilled", "Заявка выполнена"
        RESERVATION_CANCELLED = "reservation_cancelled", "Заявка отменена"
        RESERVATION_EXPIRED = "reservation_expired", "Удержание истекло"
        BOOK_CREATED = "book_created", "Книга добавлена"
        BOOK_UPDATED = "book_updated", "Книга изменена"
        BOOK_DELETED = "book_deleted", "Книга удалена"
        COPY_CREATED = "copy_created", "Экземпляр добавлен"
        COPY_UPDATED = "copy_updated", "Экземпляр изменён"
        COPY_DELETED = "copy_deleted", "Экземпляр списан"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        verbose_name="Пользователь",
    )
    action = models.CharField("Действие", max_length=50, choices=Action.choices)
    entity_type = models.CharField("Тип объекта", max_length=50, blank=True)
    entity_id = models.PositiveBigIntegerField("ID объекта", null=True, blank=True)
    description = models.CharField("Описание", max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        db_table = "activity_log"
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал действий"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="activity_time_idx"),
            models.Index(fields=["user", "action"], name="activity_user_action_idx"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user_id} {self.action}"
