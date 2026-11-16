"""Демонстрация защиты от двойной выдачи на живом backend.

Запускает 10 параллельных HTTP-запросов на бронирование одного экземпляра
и показывает, что срабатывает ровно один. Требуется запущенный сервер:

    python manage.py runserver
    python scripts/concurrent_booking.py

Параметры: --base-url, --email, --password, --threads, --copy-id, --keep.
По умолчанию тестовая бронь удаляется, чтобы демонстрацию можно было
повторять; с --keep она остаётся в базе.
"""

import argparse
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402

from catalog.models import BookCopy  # noqa: E402
from loans.models import Loan, LoanStatusHistory  # noqa: E402
from loans.statuses import BLOCKING_STATUSES  # noqa: E402
from reservations.models import Reservation  # noqa: E402
from users.models import ActivityLog  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEMO_OFFSET_DAYS = 120
DEFAULT_THREADS = 10


def request_json(method, url, payload=None, token=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return error.code, json.loads(raw) if raw else None


def login(base_url, email, password):
    status, data = request_json(
        "POST", f"{base_url}/api/auth/login/", {"email": email, "password": password}
    )
    if status != 200 or not data:
        raise SystemExit(f"Не удалось войти ({status}): {data}")
    return data["access"]


def find_free_copy(start, due):
    now = timezone.now()
    copies = (
        BookCopy.objects.filter(is_active=True, book__is_active=True)
        .select_related("book")
        .order_by("pk")
    )
    for copy in copies:
        busy = Loan.objects.filter(
            copy=copy,
            status__in=BLOCKING_STATUSES,
            start_date__lt=due,
            due_date__gt=start,
        ).exists()
        if busy:
            continue
        held = Reservation.objects.filter(
            hold_copy=copy,
            status=Reservation.Status.READY,
            hold_until__gt=now,
        ).exists()
        if not held:
            return copy
    raise SystemExit("Не нашлось свободного экземпляра для демонстрации")


def run_requests(url, token, payload, threads):
    barrier = threading.Barrier(threads)
    results = []
    lock = threading.Lock()

    def worker():
        barrier.wait(timeout=30)
        status, body = request_json("POST", url, payload, token)
        with lock:
            results.append(
                (
                    status,
                    (body or {}).get("code"),
                    (body or {}).get("id"),
                    (body or {}).get("detail"),
                )
            )

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for worker_thread in workers:
        worker_thread.start()
    for worker_thread in workers:
        worker_thread.join(timeout=60)
    return results


def cleanup(loan_id):
    LoanStatusHistory.objects.filter(loan_id=loan_id).delete()
    ActivityLog.objects.filter(entity_type="loan", entity_id=loan_id).delete()
    Loan.objects.filter(pk=loan_id).delete()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default="reader1@library.local")
    parser.add_argument("--password", default="demo12345")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--copy-id", type=int, default=None)
    parser.add_argument("--keep", action="store_true", help="не удалять тестовую бронь")
    args = parser.parse_args()

    today = timezone.localdate()
    start = today + timedelta(days=DEMO_OFFSET_DAYS)
    due = start + timedelta(days=14)

    if args.copy_id:
        copy = BookCopy.objects.select_related("book").get(pk=args.copy_id)
    else:
        copy = find_free_copy(start, due)

    token = login(args.base_url, args.email, args.password)

    print("Демонстрация конкурентного бронирования")
    print(f"БД: {connection.vendor}, экземпляр: {copy.inventory_number} «{copy.book.title}»")
    print(f"Период: {start:%d.%m.%Y} — {due:%d.%m.%Y}, потоков: {args.threads}")
    print()

    payload = {"copy_id": copy.id, "start_date": start.isoformat()}
    results = run_requests(f"{args.base_url}/api/loans/", token, payload, args.threads)

    for status, code, loan_id, detail in results:
        tail = code or detail or ""
        print(f"  {status}  {tail}")

    created = [item for item in results if item[0] == 201]
    conflicts = [item for item in results if item[0] == 409]
    loans_in_db = Loan.objects.filter(
        copy=copy, start_date=start, due_date=due
    ).count()

    print()
    print(f"201 Created: {len(created)}, 409 Conflict: {len(conflicts)}")
    print(f"Броней в базе на этот интервал: {loans_in_db}")

    ok = (
        len(created) == 1
        and len(conflicts) == args.threads - 1
        and loans_in_db == 1
        and all(item[1] == "copy_taken" for item in conflicts)
    )
    print("Вердикт:", "OK — двойной выдачи нет" if ok else "ОШИБКА — проверьте блокировку")

    if created and not args.keep:
        cleanup(created[0][2])
        print("Тестовая бронь удалена (используйте --keep, чтобы оставить).")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
