"""Маршруты броней."""

from django.urls import path

from loans.views import LoanCollectionView, LoanDetailView, LoanStatusView

urlpatterns = [
    path("loans/", LoanCollectionView.as_view(), name="loan-list"),
    path("loans/<int:pk>/", LoanDetailView.as_view(), name="loan-detail"),
    path("loans/<int:pk>/status/", LoanStatusView.as_view(), name="loan-status"),
]
