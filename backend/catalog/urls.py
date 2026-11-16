"""Маршруты каталога."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import BookCopyDetailView, BookViewSet

router = DefaultRouter()
router.register("books", BookViewSet, basename="book")

urlpatterns = [
    path(
        "books/<int:book_id>/copies/<int:pk>/",
        BookCopyDetailView.as_view(),
        name="book-copy-detail",
    ),
    path("", include(router.urls)),
]
