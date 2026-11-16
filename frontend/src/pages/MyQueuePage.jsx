import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "../api/client";
import { cancelReservation, fetchMyReservations } from "../api/reservations";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import Pagination from "../components/Pagination";
import SiteHeader from "../components/SiteHeader";
import StatusBadge from "../components/StatusBadge";
import { formatDateTime } from "../utils/dates";
import "../styles/dashboard.css";

const STATUS_TABS = [
  { value: "", label: "Все" },
  { value: "waiting", label: "Ожидают" },
  { value: "ready", label: "Готовы к выдаче" },
  { value: "fulfilled", label: "Выполнены" },
  { value: "expired", label: "Просрочены" },
];

export default function MyQueuePage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [reservations, setReservations] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionId, setActionId] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadReservations() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchMyReservations({
          status,
          page,
          signal: controller.signal,
        });
        if (cancelled) return;
        setReservations(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setReservations([]);
        setCount(0);
        setError(
          getErrorMessage(
            requestError,
            "Не удалось загрузить очередь. Попробуйте ещё раз.",
          ),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadReservations();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [status, page, reloadKey]);

  function changeStatus(value) {
    setStatus(value);
    setPage(1);
    setActionError("");
  }

  async function cancel(reservation) {
    if (!window.confirm(`Отменить заявку на «${reservation.book.title}»?`)) return;

    setActionId(reservation.id);
    setActionError("");
    try {
      await cancelReservation(reservation.id);
      if (reservations.length === 1 && page > 1) setPage(page - 1);
      else setReloadKey((value) => value + 1);
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось отменить заявку."),
      );
    } finally {
      setActionId(null);
    }
  }

  const isEmpty = !loading && !error && reservations.length === 0;

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Личный кабинет</p>
          <h1 className="dashboard__title">Моя очередь</h1>
          <p className="dashboard__lead">
            Позиция считается по времени постановки. Когда экземпляр освободится,
            заявка станет «Готова к выдаче» и будет удерживаться 48 часов.
          </p>
        </div>

        <div className="dashboard__tabs" role="tablist" aria-label="Статусы заявок">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value || "all"}
              type="button"
              className={`dashboard__tab${
                status === tab.value ? " dashboard__tab--active" : ""
              }`}
              onClick={() => changeStatus(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {actionError && <ErrorMessage message={actionError} />}

        {error && (
          <ErrorMessage
            message={error}
            onRetry={() => setReloadKey((value) => value + 1)}
          />
        )}

        {loading && <Loader text="Загружаем вашу очередь…" />}

        {isEmpty && (
          <section className="dashboard__empty">
            <h2 className="dashboard__empty-title">
              {status ? "В этом статусе заявок нет" : "Вы пока не в очереди"}
            </h2>
            <p className="dashboard__empty-text">
              {status
                ? "Выберите другой статус или посмотрите все заявки."
                : "Если все экземпляры книги заняты, встаньте в очередь на её странице."}
            </p>
            <Link className="button button--primary" to="/catalog">
              Перейти в каталог
            </Link>
          </section>
        )}

        {!loading && !error && reservations.length > 0 && (
          <>
            <p className="dashboard__summary">Всего заявок: {count}</p>

            <ul className="record-list">
              {reservations.map((reservation) => (
                <li className="record-card" key={reservation.id}>
                  <div className="record-card__head">
                    <div>
                      <h2 className="record-card__title">
                        <Link
                          className="link"
                          to={`/books/${reservation.book.id}`}
                        >
                          {reservation.book.title}
                        </Link>
                      </h2>
                      <p className="record-card__author">
                        {reservation.book.author}
                      </p>
                    </div>
                    <StatusBadge
                      status={reservation.status}
                      kind="reservation"
                    />
                  </div>

                  <dl className="record-card__details">
                    {reservation.status === "waiting" && (
                      <div className="record-card__detail">
                        <dt>Позиция</dt>
                        <dd>{reservation.position ?? "—"}</dd>
                      </div>
                    )}
                    {reservation.status === "ready" && (
                      <div className="record-card__detail">
                        <dt>Удержание до</dt>
                        <dd>{formatDateTime(reservation.hold_until)}</dd>
                      </div>
                    )}
                    <div className="record-card__detail">
                      <dt>Поставлена</dt>
                      <dd>{formatDateTime(reservation.created_at)}</dd>
                    </div>
                    {reservation.book.year && (
                      <div className="record-card__detail">
                        <dt>Год</dt>
                        <dd>{reservation.book.year}</dd>
                      </div>
                    )}
                  </dl>

                  {(reservation.status === "waiting" ||
                    reservation.status === "ready") && (
                    <div className="record-card__actions">
                      <button
                        type="button"
                        className="button button--ghost"
                        disabled={actionId === reservation.id}
                        onClick={() => cancel(reservation)}
                      >
                        {actionId === reservation.id
                          ? "Отменяем…"
                          : "Отменить заявку"}
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>

            <Pagination page={page} count={count} onChange={setPage} />
          </>
        )}
      </main>
    </div>
  );
}
