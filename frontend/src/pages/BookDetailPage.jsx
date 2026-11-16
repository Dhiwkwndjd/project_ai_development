import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { fetchAvailability, fetchBook } from "../api/books";
import { getErrorMessage } from "../api/client";
import AvailabilityBadge from "../components/AvailabilityBadge";
import BookCover from "../components/BookCover";
import BookingPanel from "../components/BookingPanel";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import SiteHeader from "../components/SiteHeader";
import { addDays, formatDate, todayISO } from "../utils/dates";
import "../styles/book.css";

const DEFAULT_DAYS = 14;
const MAX_DAYS = 30;

const CONDITION_LABELS = {
  new: "Новый",
  good: "Хороший",
  worn: "Потрёпанный",
};

function validatePeriod(startDate, dueDate) {
  if (!startDate || !dueDate) return "Укажите обе даты";
  if (startDate < todayISO()) return "Дата начала не может быть в прошлом";
  if (dueDate <= startDate) return "Дата возврата должна быть позже даты начала";

  const days = (new Date(`${dueDate}T00:00:00`) - new Date(`${startDate}T00:00:00`)) /
    (24 * 60 * 60 * 1000);
  if (days > MAX_DAYS) return `Максимальный срок — ${MAX_DAYS} дней`;
  return "";
}

function initialPeriod() {
  const startDate = todayISO();
  return { startDate, dueDate: addDays(startDate, DEFAULT_DAYS) };
}

export default function BookDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const backTo = location.state?.from || "/catalog";
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [period, setPeriod] = useState(initialPeriod);
  const [appliedPeriod, setAppliedPeriod] = useState(initialPeriod);
  const [dateError, setDateError] = useState("");
  const [availability, setAvailability] = useState(null);
  const [availabilityLoading, setAvailabilityLoading] = useState(true);
  const [availabilityError, setAvailabilityError] = useState("");
  const [availabilityReloadKey, setAvailabilityReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadBook() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchBook(id, { signal: controller.signal });
        if (!cancelled) setBook(data);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setBook(null);
        setError(
          getErrorMessage(requestError, "Не удалось загрузить книгу. Попробуйте ещё раз."),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadBook();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadAvailability() {
      setAvailabilityLoading(true);
      setAvailabilityError("");
      try {
        const data = await fetchAvailability(id, {
          ...appliedPeriod,
          signal: controller.signal,
        });
        if (!cancelled) setAvailability(data);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setAvailability(null);
        setAvailabilityError(
          getErrorMessage(requestError, "Не удалось проверить доступность."),
        );
      } finally {
        if (!cancelled) setAvailabilityLoading(false);
      }
    }

    loadAvailability();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [id, appliedPeriod, availabilityReloadKey]);

  function handleAvailabilitySubmit(event) {
    event.preventDefault();
    const problem = validatePeriod(period.startDate, period.dueDate);
    setDateError(problem);
    if (problem) return;
    setAppliedPeriod({ startDate: period.startDate, dueDate: period.dueDate });
  }

  function handleResetPeriod() {
    const next = initialPeriod();
    setPeriod(next);
    setAppliedPeriod({ ...next });
    setDateError("");
  }

  function handleBookingChanged() {
    setReloadKey((value) => value + 1);
    setAvailabilityReloadKey((value) => value + 1);
  }

  return (
    <div className="page">
      <SiteHeader />

      <main className="book-page">
        <Link className="book-page__back" to={backTo}>
          ← Назад в каталог
        </Link>

        {loading && <Loader text="Загружаем книгу…" />}

        {error && (
          <ErrorMessage
            message={error}
            onRetry={() => setReloadKey((value) => value + 1)}
          />
        )}

        {book && !error && (
          <>
            <article className="book-detail">
              <div className="book-detail__cover">
                <BookCover book={book} large />
              </div>

              <div className="book-detail__info">
                <p className="book-detail__eyebrow">{book.genre}</p>
                <h1 className="book-detail__title">{book.title}</h1>
                <p className="book-detail__author">{book.author}</p>
                <p className="book-detail__description">
                  {book.description || "Описание пока не добавлено."}
                </p>

                <div className="book-detail__meta">
                  <div className="book-meta">
                    <span className="book-meta__label">Год издания</span>
                    <span className="book-meta__value">
                      {book.year || "—"}
                    </span>
                  </div>
                  <div className="book-meta">
                    <span className="book-meta__label">Всего экземпляров</span>
                    <span className="book-meta__value">{book.total_copies}</span>
                  </div>
                  <div className="book-meta">
                    <span className="book-meta__label">Свободно сейчас</span>
                    <span className="book-meta__value">{book.free_copies}</span>
                  </div>
                  <div className="book-meta">
                    <span className="book-meta__label">В очереди</span>
                    <span className="book-meta__value">{book.waiting_count ?? 0}</span>
                  </div>
                </div>

                <AvailabilityBadge
                  free={book.free_copies}
                  total={book.total_copies}
                />
              </div>
            </article>

            <section className="book-availability" aria-labelledby="availability-title">
              <h2 className="book-availability__title" id="availability-title">
                Свободные экземпляры на даты
              </h2>
              <p className="book-availability__lead">
                Выберите период — покажем, какие экземпляры можно взять.
              </p>

              <form
                className="book-availability__form"
                onSubmit={handleAvailabilitySubmit}
                noValidate
              >
                <div className="field">
                  <label className="field__label" htmlFor="availability-start">
                    Дата начала
                  </label>
                  <input
                    id="availability-start"
                    className={`input${dateError ? " input--invalid" : ""}`}
                    type="date"
                    value={period.startDate}
                    min={todayISO()}
                    onChange={(event) => {
                      setPeriod((prev) => ({ ...prev, startDate: event.target.value }));
                      setDateError("");
                    }}
                  />
                </div>

                <div className="field">
                  <label className="field__label" htmlFor="availability-due">
                    Дата возврата
                  </label>
                  <input
                    id="availability-due"
                    className={`input${dateError ? " input--invalid" : ""}`}
                    type="date"
                    value={period.dueDate}
                    min={period.startDate || todayISO()}
                    onChange={(event) => {
                      setPeriod((prev) => ({ ...prev, dueDate: event.target.value }));
                      setDateError("");
                    }}
                  />
                </div>

                <button
                  className="button button--primary"
                  type="submit"
                  disabled={availabilityLoading}
                >
                  Проверить
                </button>

                <button
                  className="button button--ghost"
                  type="button"
                  onClick={handleResetPeriod}
                >
                  Сбросить даты
                </button>
              </form>

              {dateError && <p className="field__error">{dateError}</p>}

              {availabilityError && (
                <ErrorMessage
                  message={availabilityError}
                  onRetry={() => setAvailabilityReloadKey((value) => value + 1)}
                />
              )}

              {availabilityLoading && <Loader text="Проверяем доступность…" />}

              {!availabilityLoading && availability && (
                <div className="book-availability__result">
                  <div className="book-availability__summary">
                    <AvailabilityBadge
                      free={availability.free_copies}
                      total={availability.total_copies}
                    />
                    <span className="book-availability__period">
                      {formatDate(availability.start_date)} —{" "}
                      {formatDate(availability.due_date)}
                    </span>
                  </div>

                  {availability.copies.length === 0 ? (
                    <p className="book-availability__empty">
                      У книги пока нет активных экземпляров.
                    </p>
                  ) : (
                    <ul className="copy-list">
                      {availability.copies.map((copy) => (
                        <li
                          key={copy.id}
                          className={`copy-list__item${
                            copy.is_available ? "" : " copy-list__item--busy"
                          }`}
                        >
                          <span className="copy-list__number">{copy.inventory_number}</span>
                          <span className="copy-list__condition">
                            {CONDITION_LABELS[copy.condition] || copy.condition}
                          </span>
                          <span className="copy-list__state">
                            {copy.is_available ? "Свободен" : "Занят"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {availability && (
                <BookingPanel
                  book={book}
                  availability={availability}
                  period={appliedPeriod}
                  onChanged={handleBookingChanged}
                />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
