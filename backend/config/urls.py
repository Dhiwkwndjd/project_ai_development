"""Корневой роутинг проекта."""

from django.contrib import admin
from django.urls import include, path

from users.admin_views import ActivityLogListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/admin/", include("users.admin_urls")),
    path("api/logs/", ActivityLogListView.as_view(), name="activity-log-list"),
    path("api/reports/", include("reports.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("loans.urls")),
    path("api/", include("reservations.urls")),
]
