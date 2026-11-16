"""Живая проверка очереди и статусов на запущенном backend.

Запуск (backend на 127.0.0.1:8000):
    .\\venv\\Scripts\\python.exe scripts\\check_queue_api.py

Скрипт создаёт отдельную книгу с одним экземпляром и проходит полный
сценарий: бронь → очередь → возврат → удержание → выполнение заявки.
В конце книга убирается из каталога, чтобы не засорять демо-данные.
Внешних зависимостей нет: только стандартная библиотека.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "http://127.0.0.1:8000/api"
PASSWORD = "demo12345"
TIMEOUT = 15

passed = 0
failed = 0


def check(name, condition, extra=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {extra}")


def call(method, path, token=None, params=None, payload=None):
    url = f"{API}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        return error.code, json.loads(body) if body else {}


def login(email):
    status, body = call("POST", "/auth/login/", payload={"email": email, "password": PASSWORD})
    assert status == 200, f"login {email}: {status} {body}"
    return body["access"]


def for_book(payload, book_id):
    """Заявка из списка «мои» именно по проверяемой книге."""
    items = [item for item in payload.get("results", []) if item["book"]["id"] == book_id]
    return items[0] if items else {}


def main():
    admin = login("admin@library.local")
    librarian = login("librarian1@library.local")
    readers = [login(f"reader{i}@library.local") for i in (1, 2, 3)]

    today = date.today()
    start = today
    due = today + timedelta(days=5)
    stamp = time.strftime("%H%M%S")

    print("1. Администратор создаёт книгу и экземпляр")
    status, book = call(
        "POST",
        "/books/",
        token=admin,
        payload={
            "title": f"Проверка очереди {today.isoformat()} {stamp}",
            "author": "Скрипт",
            "genre": "Проверка",
            "year": 2026,
        },
    )
    check("книга создана", status == 201, f"{status} {book}")

    status, copy = call(
        "POST",
        f"/books/{book['id']}/copies/",
        token=admin,
        payload={
            "inventory_number": f"CHK-{today.isoformat()}-{stamp}",
            "condition": "good",
        },
    )
    check("экземпляр создан", status == 201, f"{status} {copy}")

    print("2. Первый читатель занимает единственный экземпляр")
    status, loan = call(
        "POST",
        "/loans/",
        token=readers[0],
        payload={
            "copy_id": copy["id"],
            "start_date": start.isoformat(),
            "due_date": due.isoformat(),
        },
    )
    check("бронь создана", status == 201, f"{status} {loan}")

    status, availability = call(
        "GET",
        f"/books/{book['id']}/availability/",
        token=readers[1],
        params={"start_date": start.isoformat(), "due_date": due.isoformat()},
    )
    check("свободных экземпляров нет", availability.get("free_copies") == 0, availability)

    print("3. Очередь FIFO")
    status, first = call(
        "POST", "/reservations/", token=readers[1], payload={"book_id": book["id"]}
    )
    check("первая заявка создана", status == 201, f"{status} {first}")
    check("позиция 1", first.get("position") == 1, first)

    status, second = call(
        "POST", "/reservations/", token=readers[2], payload={"book_id": book["id"]}
    )
    check("вторая заявка создана", status == 201, f"{status} {second}")
    check("позиция 2", second.get("position") == 2, second)

    status, duplicate = call(
        "POST", "/reservations/", token=readers[2], payload={"book_id": book["id"]}
    )
    check(
        "дубль запрещён",
        status == 409 and duplicate.get("code") == "already_queued",
        duplicate,
    )

    print("4. Выдача и возврат библиотекарем")
    status, _ = call(
        "PATCH",
        f"/loans/{loan['id']}/status/",
        token=librarian,
        payload={"status": "active"},
    )
    check("книга выдана", status == 200, status)

    status, _ = call(
        "PATCH",
        f"/loans/{loan['id']}/status/",
        token=librarian,
        payload={"status": "returned"},
    )
    check("возврат принят", status == 200, status)

    status, my_queue = call("GET", "/reservations/my/", token=readers[1])
    ready = for_book(my_queue, book["id"])
    check("первый читатель получил удержание", ready.get("status") == "ready", ready)
    check("позиция удержания 1", ready.get("position") == 1, ready)
    check("экземпляр удержан", ready.get("hold_copy_id") == copy["id"], ready)

    print("5. Читатель оформляет бронь на удержанный экземпляр")
    status, hold_loan = call(
        "POST",
        "/loans/",
        token=readers[1],
        payload={
            "copy_id": copy["id"],
            "start_date": start.isoformat(),
            "due_date": due.isoformat(),
        },
    )
    check("бронь по удержанию создана", status == 201, f"{status} {hold_loan}")

    status, my_queue = call("GET", "/reservations/my/", token=readers[1])
    fulfilled = for_book(my_queue, book["id"])
    check("заявка выполнена", fulfilled.get("status") == "fulfilled", fulfilled)

    print("6. Повторный возврат передаёт удержание второму")
    call(
        "PATCH",
        f"/loans/{hold_loan['id']}/status/",
        token=librarian,
        payload={"status": "active"},
    )
    status, _ = call(
        "PATCH",
        f"/loans/{hold_loan['id']}/status/",
        token=librarian,
        payload={"status": "returned"},
    )
    check("второй возврат принят", status == 200, status)

    status, second_queue = call("GET", "/reservations/my/", token=readers[2])
    second_ready = for_book(second_queue, book["id"])
    check(
        "второй читатель получил удержание",
        second_ready.get("status") == "ready",
        second_ready,
    )

    print("7. Права")
    status, own = call("GET", "/loans/", token=readers[1])
    own_ids = {item["reader_id"] for item in own.get("results", [])}
    check(
        "читатель видит только свои брони",
        status == 200 and len(own_ids) == 1,
        own,
    )

    status, everything = call("GET", "/loans/", token=librarian)
    check(
        "библиотекарь видит все брони",
        status == 200 and everything.get("count", 0) >= 2,
        everything,
    )

    status, foreign = call(
        "PATCH",
        f"/loans/{hold_loan['id']}/status/",
        token=readers[2],
        payload={"status": "cancelled"},
    )
    check("чужая бронь скрыта", status == 404, foreign)

    status, forbidden = call(
        "PATCH",
        f"/loans/{hold_loan['id']}/status/",
        token=readers[1],
        payload={"status": "active"},
    )
    check(
        "читатель не выдаёт книгу",
        status == 403 and forbidden.get("code") == "forbidden",
        forbidden,
    )

    status, queue = call(
        "GET", "/reservations/", token=librarian, params={"book_id": book["id"]}
    )
    check("библиотекарь видит очередь по книге", queue.get("count") == 2, queue)

    status, anonymous = call("GET", "/loans/")
    check("без токена 401", status == 401, status)

    print("8. Уборка демо-данных")
    if second_ready:
        call("DELETE", f"/reservations/{second_ready['id']}/", token=readers[2])
    call("PATCH", f"/books/{book['id']}/", token=admin, payload={"is_active": False})
    print("  Книга убрана из каталога, история сохранена")

    print(f"\nИтог: {passed} успешно, {failed} с ошибками")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
