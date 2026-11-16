"""Маршруты отчётов (только роль admin)."""

from django.urls import path

from reports.views import ReportBooksCsvView, ReportLoansCsvView, ReportSummaryView

urlpatterns = [
    path("summary/", ReportSummaryView.as_view(), name="report-summary"),
    path("loans.csv", ReportLoansCsvView.as_view(), name="report-loans-csv"),
    path("books.csv", ReportBooksCsvView.as_view(), name="report-books-csv"),
]
