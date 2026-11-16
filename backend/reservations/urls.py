"""Маршруты очереди."""

from django.urls import path

from reservations.views import (
    ReservationCancelView,
    ReservationCollectionView,
    ReservationMyListView,
)

urlpatterns = [
    path(
        "reservations/my/",
        ReservationMyListView.as_view(),
        name="reservation-my",
    ),
    path(
        "reservations/",
        ReservationCollectionView.as_view(),
        name="reservation-list",
    ),
    path(
        "reservations/<int:pk>/",
        ReservationCancelView.as_view(),
        name="reservation-cancel",
    ),
]
