"""Демо-данные библиотеки: пользователи, книги, экземпляры, брони и очередь.

Запуск: python manage.py seed_demo
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Book, BookCopy
from loans.models import Loan, LoanStatusHistory
from loans.statuses import LoanStatus
from reservations.models import Reservation
from users.models import User

DEMO_PASSWORD = "demo12345"

BOOKS = [
    ("Мастер и Маргарита", "Михаил Булгаков", "Роман", "Роман о добре и зле, любви и трусости.", 1967),
    ("Преступление и наказание", "Фёдор Достоевский", "Роман", "История бывшего студента Раскольникова.", 1866),
    ("Война и мир", "Лев Толстой", "Роман", "Эпопея о России эпохи наполеоновских войн.", 1869),
    ("Анна Каренина", "Лев Толстой", "Роман", "Трагедия любви в высшем обществе.", 1878),
    ("Отцы и дети", "Иван Тургенев", "Роман", "Конфликт поколений и нигилизм Базарова.", 1862),
    ("Мёртвые души", "Николай Гоголь", "Поэма", "Похождения Чичикова по России.", 1842),
    ("Герой нашего времени", "Михаил Лермонтов", "Роман", "Портрет поколения через Печорина.", 1840),
    ("Евгений Онегин", "Александр Пушкин", "Поэзия", "Роман в стихах о любви и скуке.", 1833),
    ("Тихий Дон", "Михаил Шолохов", "Роман", "Жизнь донского казачества в эпоху перемен.", 1940),
    ("Доктор Живаго", "Борис Пастернак", "Роман", "Судьба врача на фоне истории XX века.", 1957),
    ("Собачье сердце", "Михаил Булгаков", "Повесть", "Эксперимент профессора Преображенского.", 1987),
    ("Пикник на обочине", "Аркадий и Борис Стругацкие", "Фантастика", "Сталкеры и Зона.", 1972),
    ("Солярис", "Станислав Лем", "Фантастика", "Разумный океан и границы познания.", 1961),
    ("1984", "Джордж Оруэлл", "Антиутопия", "Мир тотального контроля.", 1949),
    ("О дивный новый мир", "Олдос Хаксли", "Антиутопия", "Общество потребления и счастья.", 1932),
    ("Три товарища", "Эрих Мария Ремарк", "Роман", "Дружба и любовь после войны.", 1936),
    ("Над пропастью во ржи", "Джером Сэлинджер", "Роман", "Взгляд подростка на взрослый мир.", 1951),
    ("Убить пересмешника", "Харпер Ли", "Роман", "Справедливость глазами ребёнка.", 1960),
    ("Старик и море", "Эрнест Хемингуэй", "Повесть", "История рыбака Сантьяго.", 1952),
    ("Имя розы", "Умберто Эко", "Детектив", "Монастырь, тайна и средневековая библиотека.", 1980),
]


class Command(BaseCommand):
    help = "Создать демо-данные: пользователей, книги, брони и очередь"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD,
            help="Пароль для всех демо-пользователей",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        admin = self.create_users(password)
        books = self.create_books()
        copies = self.create_copies(books)
        self.create_loans(copies)
        self.create_reservations(books, copies)

        self.stdout.write(self.style.SUCCESS("Демо-данные готовы"))
        self.stdout.write(f"Пользователей: {User.objects.count()}")
        self.stdout.write(f"Книг: {Book.objects.count()}")
        self.stdout.write(f"Экземпляров: {BookCopy.objects.count()}")
        self.stdout.write(f"Броней: {Loan.objects.count()}")
        self.stdout.write(f"Заявок в очереди: {Reservation.objects.count()}")
        self.stdout.write("")
        self.stdout.write("Логины (пароль у всех: %s):" % password)
        self.stdout.write(f"  admin:     {admin.email}")
        self.stdout.write("  librarian: librarian1@library.local ... librarian3@library.local")
        self.stdout.write("  reader:    reader1@library.local ... reader10@library.local")

    def create_users(self, password):
        admin, _ = User.objects.update_or_create(
            email="admin@library.local",
            defaults={
                "full_name": "Администратор библиотеки",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        admin.set_password(password)
        admin.save(update_fields=["password"])

        for i in range(1, 4):
            user, _ = User.objects.update_or_create(
                email=f"librarian{i}@library.local",
                defaults={
                    "full_name": f"Библиотекарь {i}",
                    "role": User.Role.LIBRARIAN,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])

        for i in range(1, 11):
            user, _ = User.objects.update_or_create(
                email=f"reader{i}@library.local",
                defaults={
                    "full_name": f"Читатель {i}",
                    "phone": f"+7 900 000-00-{i:02d}",
                    "role": User.Role.READER,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])

        return admin

    def create_books(self):
        books = []
        for index, (title, author, genre, description, year) in enumerate(BOOKS, start=1):
            book, _ = Book.objects.update_or_create(
                title=title,
                defaults={
                    "author": author,
                    "genre": genre,
                    "year": year,
                    "description": description,
                    "cover_url": f"https://picsum.photos/seed/library{index}/240/360",
                    "is_active": True,
                },
            )
            books.append(book)
        return books

    def create_copies(self, books):
        copies = []
        number = 1
        for index, book in enumerate(books):
            copies.append(self.get_copy(book, number))
            number += 1
            # Первым десяти книгам — второй экземпляр.
            if index < 10:
                copies.append(self.get_copy(book, number))
                number += 1
        return copies

    def get_copy(self, book, number):
        copy, _ = BookCopy.objects.update_or_create(
            inventory_number=f"INV-{number:03d}",
            defaults={
                "book": book,
                "condition": BookCopy.Condition.GOOD,
                "is_active": True,
            },
        )
        return copy

    def create_loans(self, copies):
        today = timezone.localdate()
        base = today - timedelta(days=120)
        readers = list(User.objects.filter(role=User.Role.READER).order_by("email"))
        librarian = User.objects.filter(role=User.Role.LIBRARIAN).order_by("email").first()

        if not readers:
            return

        def add_loan(copy, reader, start, due, status):
            loan, created = Loan.objects.get_or_create(
                copy=copy,
                start_date=start,
                defaults={
                    "reader": reader,
                    "due_date": due,
                    "status": status,
                },
            )
            if created:
                self.add_history(loan, status, librarian)
            return loan

        # 30 исторических броней: по одной на экземпляр и вторая для первых десяти.
        for index, copy in enumerate(copies):
            start = base + timedelta(days=index * 2)
            status = LoanStatus.CANCELLED if index % 6 == 0 else LoanStatus.RETURNED
            add_loan(copy, readers[index % len(readers)], start, start + timedelta(days=10), status)

        for index, copy in enumerate(copies[:10]):
            start = base + timedelta(days=index * 2 + 20)
            add_loan(
                copy,
                readers[(index + 3) % len(readers)],
                start,
                start + timedelta(days=10),
                LoanStatus.RETURNED,
            )

        # Текущие выдачи и новые брони — на свободные экземпляры.
        for index, copy in enumerate(copies[:3]):
            add_loan(
                copy,
                readers[(index + 1) % len(readers)],
                today - timedelta(days=2),
                today + timedelta(days=12),
                LoanStatus.ACTIVE,
            )
        for index, copy in enumerate(copies[3:5]):
            add_loan(
                copy,
                readers[(index + 5) % len(readers)],
                today + timedelta(days=1),
                today + timedelta(days=15),
                LoanStatus.CREATED,
            )

    def add_history(self, loan, status, changed_by):
        if status == LoanStatus.RETURNED:
            LoanStatusHistory.objects.create(
                loan=loan, old_status=LoanStatus.CREATED, new_status=LoanStatus.ACTIVE,
                changed_by=changed_by,
            )
            LoanStatusHistory.objects.create(
                loan=loan, old_status=LoanStatus.ACTIVE, new_status=LoanStatus.RETURNED,
                changed_by=changed_by,
            )
        elif status == LoanStatus.ACTIVE:
            LoanStatusHistory.objects.create(
                loan=loan, old_status=LoanStatus.CREATED, new_status=LoanStatus.ACTIVE,
                changed_by=changed_by,
            )
        elif status == LoanStatus.CANCELLED:
            LoanStatusHistory.objects.create(
                loan=loan, old_status=LoanStatus.CREATED, new_status=LoanStatus.CANCELLED,
                changed_by=changed_by,
            )

    def create_reservations(self, books, copies):
        now = timezone.now()
        readers = list(User.objects.filter(role=User.Role.READER).order_by("email"))
        if not readers:
            return

        ready_book = books[15]
        hold_copy = ready_book.copies.filter(is_active=True).first()
        if hold_copy:
            Reservation.objects.update_or_create(
                book=ready_book,
                reader=readers[0],
                status=Reservation.Status.READY,
                defaults={
                    "hold_copy": hold_copy,
                    "hold_until": now + timedelta(hours=48),
                },
            )

        for index in range(1, 5):
            Reservation.objects.get_or_create(
                book=books[index],
                reader=readers[index],
                status=Reservation.Status.WAITING,
            )
