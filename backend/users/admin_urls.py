"""Маршруты админ-панели (только роль admin)."""

from django.urls import path

from users.admin_views import (
    AdminUserCollectionView,
    AdminUserRoleView,
    AdminUserStatusView,
)

urlpatterns = [
    path("users/", AdminUserCollectionView.as_view(), name="admin-user-list"),
    path(
        "users/<int:pk>/role/",
        AdminUserRoleView.as_view(),
        name="admin-user-role",
    ),
    path(
        "users/<int:pk>/status/",
        AdminUserStatusView.as_view(),
        name="admin-user-status",
    ),
]
