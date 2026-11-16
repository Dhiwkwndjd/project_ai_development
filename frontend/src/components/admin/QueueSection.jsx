import { useEffect, useState } from "react";

import { getErrorMessage } from "../../api/client";
import { fetchReservations } from "../../api/reservations";
import ErrorMessage from "../ErrorMessage";
import Loader from "../Loader";
import Pagination from "../Pagination";
import StatusBadge from "../StatusBadge";
import { formatDateTime } from "../../utils/dates";

const STATUS_OPTIONS = [
  { value: "waiting,ready", label: "Текущая очередь" },
  { value: "waiting", label: "Только ожидают" },
  { value: "ready", label: "Только удержания" },
  { value: "expired", label: "Просроченные" },
  { value: "fulfilled", label: "Выполненные" },
  { value: "", label: "Все" },
];

/** Все заявки очереди с группировкой по книге. */
export default function QueueSection() {
  const [status, setStatus] = useState("waiting,ready");
  const [page, setPage] = useState(1);

  const [reservations, setReservations] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadQueue() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchReservations({
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
        setError(getErrorMessage(requestError, "Не удалось загрузить очередь."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadQueue();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [status, page, reloadKey]);

  const groups = reservations.reduce((items, reservation) => {
    const last = items[items.length - 1];
    if (last && last.book.id === reservation.book.id) {
      last.items.push(reservation);
    } else {
      items.push({ book: reservation.book, items: [reservation] });
    }
    return items;
  }, []);

  const isEmpty = !loading && !error && reservations.length === 0;

  return (
    <section>
      <div className="admin-filters">
        <div className="field">
          <label className="field__label" htmlFor="admin-queue-status">
            Статус заявок
          </label>
          <select
            id="admin-queue-status"
            className="input"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <ErrorMessage
          message={error}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      )}

      {loading && <Loader text="Загружаем очередь…" />}

      {isEmpty && (
        <section className="dashboard__empty">
          <h2 className="dashboard__empty-title">
            В выбранном статусе заявок нет
          </h2>
          <p className="dashboard__empty-text">
            Выберите другой статус — очередь появится, когда читатели начнут
            бронировать занятые книги.
          </p>
        </section>
      )}

      {!loading && !error && reservations.length > 0 && (
        <>
          <p className="dashboard__summary">Всего заявок: {count}</p>

          {groups.map((group) => (
            <section className="queue-group" key={group.book.id}>
              <header className="queue-group__head">
                <h2 className="queue-group__title">{group.book.title}</h2>
                <span className="queue-group__author">
                  {group.book.author}
                </span>
              </header>

              <ul className="queue-list">
                {group.items.map((reservation) => (
                  <li className="queue-row" key={reservation.id}>
                    <div className="queue-row__reader">
                      <span className="queue-row__name">
                        {reservation.reader_name}
                      </span>
                      <span className="queue-row__email">
                        {reservation.reader_email}
                      </span>
                    </div>

                    <div className="queue-row__meta">
                      <StatusBadge
                        status={reservation.status}
                        kind="reservation"
                      />
                      {reservation.status === "waiting" && (
                        <span>Позиция {reservation.position ?? "—"}</span>
                      )}
                      {reservation.status === "ready" && (
                        <span>
                          Удержание до {formatDateTime(reservation.hold_until)}
                        </span>
                      )}
                      <span className="queue-row__date">
                        {formatDateTime(reservation.created_at)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <Pagination page={page} count={count} onChange={setPage} />
        </>
      )}
    </section>
  );
}
