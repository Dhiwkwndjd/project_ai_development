"""Тесты журнала действий: доступ, фильтры и формат ответа."""

from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import ActivityLog, User

LOGS_URL = "/api/logs/"
PASSWORD = "StrongPass123!"


def make_user(email, role):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name="Тестовый Пользователь", role=role
    )


def at(day, hour=12):
    naive = datetime(2026, 1, day, hour, 0)
    return timezone.make_aware(naive, timezone.get_current_timezone())


class ActivityLogApiTests(APITestCase):
    """`GET /api/logs/` — только admin, с фильтрами по пользователю и дате."""

    def setUp(self):
        self.admin = make_user("admin@test.local", User.Role.ADMIN)
        self.librarian = make_user("librarian@test.local", User.Role.LIBRARIAN)
        self.reader = make_user("reader@test.local", User.Role.READER)

        self.reader_log = self.add_log(
            self.reader, ActivityLog.Action.LOGIN, at(10), "Вход читателя"
        )
        self.librarian_log = self.add_log(
            self.librarian,
            ActivityLog.Action.LOAN_STATUS_CHANGED,
            at(15),
            "Выдача экземпляра",
        )
        self.old_log = self.add_log(
            self.reader, ActivityLog.Action.LOGOUT, at(3), "Старый выход"
        )

    def add_log(self, user, action, created_at, description):
        entry = ActivityLog.objects.create(
            user=user, action=action, description=description
        )
        ActivityLog.objects.filter(pk=entry.pk).update(created_at=created_at)
        return entry

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_reader_and_librarian_cannot_read_logs(self):
        for user in (self.reader, self.librarian):
            self.authenticate(user)
            response = self.client.get(LOGS_URL)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(response.data["code"], "forbidden")

    def test_anonymous_gets_401(self):
        response = self.client.get(LOGS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_sees_who_when_and_what(self):
        self.authenticate(self.admin)

        response = self.client.get(LOGS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        first = response.data["results"][0]
        self.assertEqual(first["id"], self.librarian_log.id)
        self.assertEqual(first["user"]["email"], "librarian@test.local")
        self.assertEqual(first["action"], ActivityLog.Action.LOAN_STATUS_CHANGED)
        self.assertEqual(first["action_label"], "Смена статуса брони")
        self.assertEqual(first["description"], "Выдача экземпляра")
        self.assertIsNotNone(first["created_at"])

    def test_filter_by_user_id_and_email(self):
        self.authenticate(self.admin)

        by_id = self.client.get(LOGS_URL, {"user_id": self.reader.id})
        by_email = self.client.get(LOGS_URL, {"user_email": "librarian@"})

        self.assertEqual(by_id.data["count"], 2)
        self.assertEqual(by_email.data["count"], 1)
        self.assertEqual(by_email.data["results"][0]["id"], self.librarian_log.id)

    def test_filter_by_date_range(self):
        self.authenticate(self.admin)

        response = self.client.get(
            LOGS_URL, {"date_from": "2026-01-08", "date_to": "2026-01-20"}
        )

        self.assertEqual(response.data["count"], 2)
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(self.reader_log.id, ids)
        self.assertIn(self.librarian_log.id, ids)
        self.assertNotIn(self.old_log.id, ids)

    def test_filter_by_action(self):
        self.authenticate(self.admin)

        response = self.client.get(LOGS_URL, {"action": ActivityLog.Action.LOGIN})

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.reader_log.id)

    def test_invalid_filters_return_400(self):
        self.authenticate(self.admin)

        bad_date = self.client.get(
            LOGS_URL, {"date_from": "2026-02-01", "date_to": "2026-01-01"}
        )
        bad_action = self.client.get(LOGS_URL, {"action": "unknown"})

        for response in (bad_date, bad_action):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["code"], "validation_error")
