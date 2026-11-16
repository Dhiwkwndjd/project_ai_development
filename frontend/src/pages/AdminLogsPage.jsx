import { useEffect, useState } from "react";

import { getErrorMessage } from "../api/client";
import { fetchLogs } from "../api/logs";
import AdminNav from "../components/admin/AdminNav";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import Pagination from "../components/Pagination";
import SiteHeader from "../components/SiteHeader";
import { formatDateTime } from "../utils/dates";
import "../styles/dashboard.css";
import "../styles/admin.css";

const ACTION_OPTIONS = [
  { value: "", label: "Все действия" },
  { value: "register", label: "Регистрация" },
  { value: "login", label: "Вход" },
  { value: "logout", label: "Выход" },
  { value: "loan_created", label: "Создание брони" },
  { value: "loan_status_changed", label: "Смена статуса брони" },
  { value: "reservation_created", label: "Постановка в очередь" },
  { value: "reservation_ready", label: "Удержание экземпляра" },
  { value: "reservation_fulfilled", label: "Заявка выполнена" },
  { value: "reservation_cancelled", label: "Заявка отменена" },
  { value: "reservation_expired", label: "Удержание истекло" },
];

/** Журнал действий: кто, когда и что сделал. */
export default function AdminLogsPage() {
  const [userQuery, setUserQuery] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const [logs, setLogs] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadLogs() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchLogs({
          userEmail,
          action,
          dateFrom,
          dateTo,
          page,
          signal: controller.signal,
        });
        if (cancelled) return;
        setLogs(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setLogs([]);
        setCount(0);
        setError(getErrorMessage(requestError, "Не удалось загрузить журнал."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadLogs();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [userEmail, action, dateFrom, dateTo, page, reloadKey]);

  function applyUser(event) {
    event.preventDefault();
    setUserEmail(userQuery.trim());
    setPage(1);
  }

  function resetFilters() {
    setUserQuery("");
    setUserEmail("");
    setAction("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  const isEmpty = !loading && !error && logs.length === 0;

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard admin">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Администрирование</p>
          <h1 className="dashboard__title">Журнал действий</h1>
          <p className="dashboard__lead">
            Все значимые события проекта: вход и выход, брони, выдача,
            возвраты и очередь. Фильтры помогают найти действия пользователя
            за нужные даты.
          </p>
        </div>

        <AdminNav />

        <div className="admin-filters">
          <form className="admin-filter-form" onSubmit={applyUser}>
            <div className="field">
              <label className="field__label" htmlFor="log-user">
                Пользователь (email)
              </label>
              <input
                id="log-user"
                className="input"
                type="search"
                placeholder="reader@library.local"
                value={userQuery}
                onChange={(event) => setUserQuery(event.target.value)}
              />
            </div>
            <button type="submit" className="button">
              Найти
            </button>
          </form>

          <div className="field">
            <label className="field__label" htmlFor="log-action">
              Действие
            </label>
            <select
              id="log-action"
              className="input"
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setPage(1);
              }}
            >
              {ACTION_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="log-date-from">
              Дата с
            </label>
            <input
              id="log-date-from"
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
            <label className="field__label" htmlFor="log-date-to">
              Дата по
            </label>
            <input
              id="log-date-to"
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

        {loading && <Loader text="Загружаем журнал…" />}

        {isEmpty && (
          <section className="dashboard__empty">
            <h2 className="dashboard__empty-title">Записей не найдено</h2>
            <p className="dashboard__empty-text">
              Измените пользователя, действие или период — журнал покажет
              события за выбранные даты.
            </p>
          </section>
        )}

        {!loading && !error && logs.length > 0 && (
          <>
            <p className="dashboard__summary">Всего записей: {count}</p>

            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Когда</th>
                    <th>Кто</th>
                    <th>Действие</th>
                    <th>Объект</th>
                    <th>Описание</th>
                    <th>IP</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatDateTime(log.created_at)}</td>
                      <td>
                        {log.user ? (
                          <>
                            <span className="admin-table__strong">
                              {log.user.full_name}
                            </span>
                            <span className="admin-table__muted">
                              {log.user.email}
                            </span>
                          </>
                        ) : (
                          "Система"
                        )}
                      </td>
                      <td>{log.action_label}</td>
                      <td>
                        {log.entity_type
                          ? `${log.entity_type} #${log.entity_id ?? "—"}`
                          : "—"}
                      </td>
                      <td>{log.description || "—"}</td>
                      <td>{log.ip_address || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination page={page} count={count} onChange={setPage} />
          </>
        )}
      </main>
    </div>
  );
}
