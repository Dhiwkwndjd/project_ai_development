import { useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "../api/client";
import { createLoan } from "../api/loans";
import { cancelReservation, createReservation } from "../api/reservations";
import { useAuth } from "../auth/context";
import { formatDate, formatDateTime } from "../utils/dates";
import ErrorMessage from "./ErrorMessage";

/** Действия читателя на странице книги: бронь, очередь, удержание. */
export default function BookingPanel({ book, availability, period, onChanged }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  if (!availability) return null;

  if (user.role !== "reader") {
    return (
      <p className="booking-panel__note">
        Оформление брони доступно читателям. Сотрудник работает с выдачами в
        разделе «Выдача».
      </p>
    );
  }

  const reservation = availability.my_reservation;
  const freeCopies = availability.available_copies || [];

  async function run(action, successText) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(successText);
      onChanged();
    } catch (requestError) {
      setError(
        getErrorMessage(requestError, "Не удалось выполнить действие. Попробуйте ещё раз."),
      );
    } finally {
      setBusy(false);
    }
  }

  function borrow(copyId) {
    return run(
      () =>
        createLoan({
          copyId,
          startDate: period.startDate,
          dueDate: period.dueDate,
        }),
      "Бронь создана. Библиотекарь выдаст книгу, когда вы придёте.",
    );
  }

  function joinQueue() {
    return run(
      () => createReservation(book.id),
      "Вы встали в очередь. Мы покажем вашу позицию в разделе «Моя очередь».",
    );
  }

  function cancelHold() {
    if (!reservation) return undefined;
    if (!window.confirm("Отменить заявку в очереди?")) return undefined;
    return run(
      () => cancelReservation(reservation.id),
      "Заявка отменена. Экземпляр перейдёт следующему читателю.",
    );
  }

  let action = null;

  if (!availability.total_copies) {
    action = (
      <p className="booking-panel__note">
        У книги нет активных экземпляров, поэтому очередь недоступна.
      </p>
    );
  } else if (reservation?.status === "ready") {
    action = (
      <>
        <p className="booking-panel__message booking-panel__message--hold">
          За вами удержан экземпляр
          {reservation.hold_until
            ? ` до ${formatDateTime(reservation.hold_until)}`
            : ""}
          . Оформите бронь, чтобы забрать книгу.
        </p>
        <div className="booking-panel__actions">
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={() => borrow(reservation.hold_copy_id || freeCopies[0]?.id)}
          >
            {busy ? "Оформляем…" : "Оформить бронь"}
          </button>
          <button
            type="button"
            className="button button--ghost"
            disabled={busy}
            onClick={cancelHold}
          >
            Отменить заявку
          </button>
        </div>
      </>
    );
  } else if (reservation?.status === "waiting") {
    action = (
      <>
        <p className="booking-panel__message booking-panel__message--hold">
          Вы в очереди. Позиция: {reservation.position ?? "—"}. Заявка
          автоматически станет готова, когда экземпляр освободится.
        </p>
        <div className="booking-panel__actions">
          <Link className="button button--ghost" to="/my/queue">
            Моя очередь
          </Link>
          <button
            type="button"
            className="button button--ghost"
            disabled={busy}
            onClick={cancelHold}
          >
            Отменить заявку
          </button>
        </div>
      </>
    );
  } else if (availability.my_loan) {
    action = (
      <>
        <p className="booking-panel__message booking-panel__message--hold">
          У вас уже есть бронь на эту книгу
          {availability.my_loan.due_date
            ? ` до ${formatDate(availability.my_loan.due_date)}`
            : ""}
          .
        </p>
        <div className="booking-panel__actions">
          <Link className="button button--ghost" to="/my">
            Мои брони
          </Link>
        </div>
      </>
    );
  } else if (freeCopies.length > 0) {
    action = (
      <div className="booking-panel__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={busy}
          onClick={() => borrow(freeCopies[0].id)}
        >
          {busy ? "Бронируем…" : "Забронировать"}
        </button>
        <span className="booking-panel__hint">
          Свободно экземпляров: {availability.free_copies}
        </span>
      </div>
    );
  } else {
    action = (
      <>
        <p className="booking-panel__message">
          На выбранные даты свободных экземпляров нет. В очереди ожидают:{" "}
          {availability.waiting_count}.
        </p>
        <div className="booking-panel__actions">
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={joinQueue}
          >
            {busy ? "Встаём в очередь…" : "Встать в очередь"}
          </button>
          <Link className="button button--ghost" to="/my/queue">
            Моя очередь
          </Link>
        </div>
      </>
    );
  }

  return (
    <section className="booking-panel" aria-label="Бронирование">
      {action}
      {error && <ErrorMessage message={error} />}
      {message && (
        <p className="booking-panel__success" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
