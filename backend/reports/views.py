"""Эндпоинты отчётов и CSV. Доступ только администратору."""

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.serializers import PeriodQuerySerializer
from reports.services import books_csv, build_summary, loans_csv
from users.api import ApiErrorMixin
from users.permissions import IsAdmin


def parse_period(request):
    serializer = PeriodQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def csv_response(filename, content):
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ReportSummaryView(ApiErrorMixin, APIView):
    """Сводка за период: события, топ книг и загрузка фонда."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(build_summary(parse_period(request)))


class ReportLoansCsvView(ApiErrorMixin, APIView):
    """CSV с бронями за период."""

    permission_classes = [IsAdmin]

    def get(self, request):
        filters = parse_period(request)
        content = loans_csv(
            date_from=filters.get("date_from"), date_to=filters.get("date_to")
        )
        return csv_response("loans.csv", content)


class ReportBooksCsvView(ApiErrorMixin, APIView):
    """CSV со всем фондом и количеством экземпляров."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return csv_response("books.csv", books_csv())
