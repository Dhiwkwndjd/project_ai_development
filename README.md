# Библиотека: бронирование книг

Веб-приложение: каталог книг, бронирование экземпляров, очередь и удержание на 48 часов при возврате, роли читатель / библиотекарь / администратор.

## Что нужно

- Python 3.12+
- Node.js 18+

База данных — SQLite (`backend/db.sqlite3`), отдельный сервер не нужен.

## Запуск

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Откройте `backend/.env` и задайте `DJANGO_SECRET_KEY` (любой длинный случайный текст), затем:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Backend: http://127.0.0.1:8000/api/

### 2. Frontend

В отдельном терминале:

```bash
cd frontend
npm install
npm run dev
```

Приложение: http://localhost:5173

## Демо-логины

Пароль у всех: `demo12345`

| Роль | Email |
|------|-------|
| Администратор | `admin@library.local` |
| Библиотекарь | `librarian1@library.local` |
| Читатель | `reader1@library.local` |
