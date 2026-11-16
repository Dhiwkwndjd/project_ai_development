"""Тесты авторизации и ролей."""

from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import ActivityLog, User
from users.permissions import IsAdmin, IsLibrarian, IsOwnerOrStaff

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"
ADMIN_USERS_URL = "/api/admin/users/"

PASSWORD = "StrongPass123!"


def create_user(email, role=User.Role.READER, password=PASSWORD):
    return User.objects.create_user(
        email=email, password=password, full_name="Тестовый пользователь", role=role
    )


class AuthApiTests(APITestCase):
    def setUp(self):
        self.reader = create_user("reader@test.local")
        self.admin = create_user("admin@test.local", role=User.Role.ADMIN)

    def login(self, email="reader@test.local", password=PASSWORD):
        return self.client.post(LOGIN_URL, {"email": email, "password": password})

    def test_register_creates_reader(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "email": "new@test.local",
                "password": PASSWORD,
                "full_name": "Новый Читатель",
                "phone": "+7 999 111-22-33",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new@test.local")
        self.assertEqual(user.role, User.Role.READER)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn("password", response.data)

    def test_register_ignores_role_from_request(self):
        response = self.client.post(
            REGISTER_URL,
            {
                "email": "sneaky@test.local",
                "password": PASSWORD,
                "full_name": "Хитрый Пользователь",
                "role": User.Role.ADMIN,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="sneaky@test.local").role, User.Role.READER)

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            REGISTER_URL,
            {"email": "reader@test.local", "password": PASSWORD, "full_name": "Дубль"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("email", response.data["fields"])
        self.assertEqual(User.objects.filter(email="reader@test.local").count(), 1)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            REGISTER_URL,
            {"email": "weak@test.local", "password": "123", "full_name": "Слабый"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="weak@test.local").exists())

    def test_login_returns_tokens_and_user(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "reader@test.local")
        self.assertEqual(response.data["user"]["role"], User.Role.READER)

    def test_login_rejects_wrong_password(self):
        response = self.login(password="WrongPass999!")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "no_active_account")
        self.assertIn("detail", response.data)

    def test_login_ignores_stale_authorization_header(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired.token.value")

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_register_ignores_stale_authorization_header(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired.token.value")

        response = self.client.post(
            REGISTER_URL,
            {
                "email": "fresh@test.local",
                "password": PASSWORD,
                "full_name": "Новый Читатель",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_refresh_returns_new_access(self):
        tokens = self.login().data
        response = self.client.post(REFRESH_URL, {"refresh": tokens["refresh"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_ignores_stale_authorization_header(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expired.token.value")

        response = self.client.post(REFRESH_URL, {"refresh": tokens["refresh"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_invalid_refresh_has_code(self):
        response = self.client.post(REFRESH_URL, {"refresh": "not-a-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "token_not_valid")
        self.assertIn("detail", response.data)

    def test_logout_blacklists_refresh_token(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        logout = self.client.post(LOGOUT_URL, {"refresh": tokens["refresh"]})
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        self.client.credentials()
        refresh = self.client.post(REFRESH_URL, {"refresh": tokens["refresh"]})
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_refresh_token(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = self.client.post(LOGOUT_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        response = self.client.post(LOGOUT_URL, {"refresh": "whatever"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "reader@test.local")

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(ME_URL).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_activity_log_records_register_login_logout(self):
        self.client.post(
            REGISTER_URL,
            {"email": "logged@test.local", "password": PASSWORD, "full_name": "Журнал"},
        )
        tokens = self.login("logged@test.local").data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.client.post(LOGOUT_URL, {"refresh": tokens["refresh"]})

        actions = list(
            ActivityLog.objects.filter(user__email="logged@test.local")
            .order_by("created_at")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [ActivityLog.Action.REGISTER, ActivityLog.Action.LOGIN, ActivityLog.Action.LOGOUT],
        )


class AdminUserApiTests(APITestCase):
    """Админ-панель пользователей: доступ и основные операции."""

    def setUp(self):
        self.admin = create_user("admin@test.local", role=User.Role.ADMIN)
        self.librarian = create_user(
            "librarian@test.local", role=User.Role.LIBRARIAN
        )
        self.reader = create_user("reader@test.local")

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_reader_cannot_list_users(self):
        self.authenticate(self.reader)

        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "forbidden")

    def test_librarian_cannot_list_users(self):
        self.authenticate(self.librarian)

        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_list_users(self):
        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "unauthorized")

    def test_admin_lists_users_with_pagination(self):
        self.authenticate(self.admin)

        response = self.client.get(ADMIN_USERS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertIn("results", response.data)

    def test_admin_searches_users_by_name_and_email(self):
        self.authenticate(self.admin)

        by_email = self.client.get(ADMIN_USERS_URL, {"search": "reader@"})
        by_name = self.client.get(ADMIN_USERS_URL, {"search": "Тестовый"})

        self.assertEqual(by_email.data["count"], 1)
        self.assertEqual(by_email.data["results"][0]["email"], "reader@test.local")
        self.assertEqual(by_name.data["count"], 3)

    def test_admin_filters_users_by_role_and_status(self):
        self.authenticate(self.admin)

        response = self.client.get(ADMIN_USERS_URL, {"role": "librarian"})

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.librarian.id)

    def test_invalid_role_filter_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.get(ADMIN_USERS_URL, {"role": "owner"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_admin_creates_librarian(self):
        self.authenticate(self.admin)

        response = self.client.post(
            ADMIN_USERS_URL,
            {
                "email": "new-librarian@test.local",
                "password": PASSWORD,
                "full_name": "Новый Библиотекарь",
                "phone": "+7 900 000-00-00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], User.Role.LIBRARIAN)
        self.assertNotIn("password", response.data)
        user = User.objects.get(email="new-librarian@test.local")
        self.assertTrue(user.check_password(PASSWORD))

    def test_create_librarian_ignores_role_from_request(self):
        self.authenticate(self.admin)

        response = self.client.post(
            ADMIN_USERS_URL,
            {
                "email": "sneaky-librarian@test.local",
                "password": PASSWORD,
                "full_name": "Хитрый Библиотекарь",
                "role": User.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="sneaky-librarian@test.local")
        self.assertEqual(user.role, User.Role.LIBRARIAN)

    def test_create_librarian_with_duplicate_email_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            ADMIN_USERS_URL,
            {
                "email": "reader@test.local",
                "password": PASSWORD,
                "full_name": "Дубль",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertIn("email", response.data["fields"])

    def test_create_librarian_with_weak_password_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.post(
            ADMIN_USERS_URL,
            {"email": "weak@test.local", "password": "123", "full_name": "Слабый"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="weak@test.local").exists())

    def test_admin_changes_user_role(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/role/",
            {"role": User.Role.LIBRARIAN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.role, User.Role.LIBRARIAN)

    def test_invalid_role_returns_400(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/role/",
            {"role": "owner"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "validation_error")

    def test_admin_cannot_change_own_role(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.admin.id}/role/",
            {"role": User.Role.READER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "self_action")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_admin_blocks_and_unblocks_user(self):
        self.authenticate(self.admin)

        blocked = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.reader.refresh_from_db()

        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertFalse(self.reader.is_active)

        unblocked = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/status/",
            {"is_active": True},
            format="json",
        )
        self.reader.refresh_from_db()

        self.assertEqual(unblocked.status_code, status.HTTP_200_OK)
        self.assertTrue(self.reader.is_active)

    def test_blocked_user_cannot_login(self):
        self.authenticate(self.admin)
        self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/status/",
            {"is_active": False},
            format="json",
        )
        self.client.credentials()

        response = self.client.post(
            LOGIN_URL, {"email": "reader@test.local", "password": PASSWORD}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_block_self(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.admin.id}/status/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "self_action")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_reader_cannot_change_role(self):
        self.authenticate(self.reader)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/role/",
            {"role": User.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.role, User.Role.READER)

    def test_librarian_cannot_block_user(self):
        self.authenticate(self.librarian)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}{self.reader.id}/status/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.reader.refresh_from_db()
        self.assertTrue(self.reader.is_active)

    def test_unknown_user_returns_404(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            f"{ADMIN_USERS_URL}999999/role/",
            {"role": User.Role.READER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "not_found")


class RolePermissionTests(APITestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = create_user("admin2@test.local", role=User.Role.ADMIN)
        self.librarian = create_user("librarian@test.local", role=User.Role.LIBRARIAN)
        self.reader = create_user("reader2@test.local")
        self.other_reader = create_user("reader3@test.local")

    def request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_is_admin_allows_only_admin(self):
        permission = IsAdmin()
        self.assertTrue(permission.has_permission(self.request_for(self.admin), None))
        self.assertFalse(permission.has_permission(self.request_for(self.librarian), None))
        self.assertFalse(permission.has_permission(self.request_for(self.reader), None))

    def test_is_librarian_allows_librarian_and_admin(self):
        permission = IsLibrarian()
        self.assertTrue(permission.has_permission(self.request_for(self.admin), None))
        self.assertTrue(permission.has_permission(self.request_for(self.librarian), None))
        self.assertFalse(permission.has_permission(self.request_for(self.reader), None))

    def test_owner_or_staff_allows_owner(self):
        loan = type("Loan", (), {"reader_id": self.reader.id})()
        self.assertTrue(
            IsOwnerOrStaff().has_object_permission(self.request_for(self.reader), object(), loan)
        )

    def test_owner_or_staff_denies_other_reader(self):
        loan = type("Loan", (), {"reader_id": self.reader.id})()
        self.assertFalse(
            IsOwnerOrStaff().has_object_permission(
                self.request_for(self.other_reader), object(), loan
            )
        )

    def test_owner_or_staff_allows_librarian(self):
        loan = type("Loan", (), {"reader_id": self.reader.id})()
        self.assertTrue(
            IsOwnerOrStaff().has_object_permission(
                self.request_for(self.librarian), object(), loan
            )
        )

    def test_anonymous_has_no_access(self):
        anonymous = type("Anon", (), {"is_authenticated": False})()
        self.assertFalse(IsAdmin().has_permission(self.request_for(anonymous), None))
        self.assertFalse(
            IsOwnerOrStaff().has_object_permission(
                self.request_for(anonymous), object(), type("Loan", (), {"reader_id": 1})()
            )
        )
