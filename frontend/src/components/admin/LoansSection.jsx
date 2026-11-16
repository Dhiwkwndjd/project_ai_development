import { useEffect, useState } from "react";

import { getErrorMessage } from "../../api/client";
import { fetchLoans } from "../../api/loans";
import ErrorMessage from "../ErrorMessage";
import Loader from "../Loader";
import Pagination from "../Pagination";
import StatusBadge from "../StatusBadge";
import { formatDate, formatDateTime } from "../../utils/dates";

const STATUS_OPTIONS = [
  { value: "", label: "Все статусы" },
  { value: "created,active", label: "Активные и забронированные" },
  { value: "created", label: "Только забронированные" },
  { value: "active", label: "Только выданные" },
  { value: "returned", label: "Возвращённые" },
  { value: "cancelled", label: "Отменённые" },
];

/** Все брони проекта с фильтрами по статусу и периоду. */
export default function LoansSection() {
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const [loans, setLoans] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadLoans() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchLoans({
          status,
          dateFrom,
          dateTo,
          page,
          signal: controller.signal,
        });
        if (cancelled) return;
        setLoans(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setLoans([]);
        setCount(0);
        setError(
          getErrorMessage(requestError, "Не удалось загрузить бронирования."),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadLoans();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [status, dateFrom, dateTo, page, reloadKey]);

  function resetFilters() {
    setStatus("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  const isEmpty = !loading && !error && loans.length === 0;

  return (
    <section>
      <div className="admin-filters">
        <div className="field">
          <label className="field__label" htmlFor="admin-loan-status">
            Статус
          </label>
          <select
            id="admin-loan-status"
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

        <div className="field">
          <label className="field__label" htmlFor="admin-loan-from">
            Период с
          </label>
          <input
            id="admin-loan-from"
            className="input"
            type="date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="admin-loan-to">
            Период по
          </label>
          <input
            id="admin-loan-to"
            className="input"
            type="date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              setPage(1);
            }}
          />
        </div>

        <button
          type="button"
          className="button button--ghost"
          onClick={resetFilters}
        >
          Сбросить
        </button>
      </div>

      {error && (
        <ErrorMessage
          message={error}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      )}

      {loading && <Loader text="Загружаем бронирования…" />}

      {isEmpty && (
        <section className="dashboard__empty">
          <h2 className="dashboard__empty-title">Бронирования не найдены</h2>
          <p className="dashboard__empty-text">
            Измените статус или период — показываются брони, пересекающиеся с
            выбранными датами.
          </p>
        </section>
      )}

      {!loading && !error && loans.length > 0 && (
        <>
          <p className="dashboard__summary">Всего броней: {count}</p>

          <ul className="record-list">
            {loans.map((loan) => (
              <li className="record-card" key={loan.id}>
                <div className="record-card__head">
                  <div>
                    <h2 className="record-card__title">{loan.book.title}</h2>
                    <p className="record-card__author">{loan.book.author}</p>
                  </div>
                  <StatusBadge status={loan.status} />
                </div>

                <dl className="record-card__details">
                  <div className="record-card__detail">
                    <dt>Читатель</dt>
                    <dd>
                      {loan.reader.full_name}
                      <span className="record-card__muted">
                        {loan.reader.email}
                      </span>
                    </dd>
                  </div>
                  <div className="record-card__detail">
                    <dt>Экземпляр</dt>
                    <dd>{loan.copy.inventory_number}</dd>
                  </div>
                  <div className="record-card__detail">
                    <dt>Период</dt>
                    <dd>
                      {formatDate(loan.start_date)} —{" "}
                      {formatDate(loan.due_date)}
                    </dd>
                  </div>
                  <div className="record-card__detail">
                    <dt>Создана</dt>
                    <dd>{formatDateTime(loan.created_at)}</dd>
                  </div>
                </dl>

                {loan.comment && (
                  <p className="record-card__comment">{loan.comment}</p>
                )}
              </li>
            ))}
          </ul>

          <Pagination page={page} count={count} onChange={setPage} />
        </>
      )}
    </section>
  );
}
