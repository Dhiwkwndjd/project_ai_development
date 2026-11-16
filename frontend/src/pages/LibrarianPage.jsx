import { useEffect, useState } from "react";

import { getErrorMessage } from "../api/client";
import { fetchLoans, updateLoanStatus } from "../api/loans";
import { fetchReservations } from "../api/reservations";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import Pagination from "../components/Pagination";
import SiteHeader from "../components/SiteHeader";
import StatusBadge from "../components/StatusBadge";
import { formatDate, formatDateTime, todayISO } from "../utils/dates";
import "../styles/dashboard.css";

const LOAN_STATUS_OPTIONS = [
  { value: "created,active", label: "Активные и забронированные" },
  { value: "created", label: "Только забронированные" },
  { value: "active", label: "Только выданные" },
  { value: "returned", label: "Возвращённые" },
  { value: "cancelled", label: "Отменённые" },
  { value: "", label: "Все" },
];

const QUEUE_STATUS_OPTIONS = [
  { value: "waiting,ready", label: "Текущая очередь" },
  { value: "waiting", label: "Только ожидают" },
  { value: "ready", label: "Только удержания" },
  { value: "expired", label: "Просроченные" },
  { value: "fulfilled", label: "Выполненные" },
  { value: "", label: "Все" },
];

export default function LibrarianPage() {
  const [tab, setTab] = useState("loans");

  const [loanStatus, setLoanStatus] = useState("created,active");
  const [activeOn, setActiveOn] = useState(todayISO());
  const [loanPage, setLoanPage] = useState(1);
  const [loans, setLoans] = useState([]);
  const [loanCount, setLoanCount] = useState(0);
  const [loansLoading, setLoansLoading] = useState(true);
  const [loansError, setLoansError] = useState("");
  const [loansReloadKey, setLoansReloadKey] = useState(0);

  const [queueStatus, setQueueStatus] = useState("waiting,ready");
  const [queuePage, setQueuePage] = useState(1);
  const [reservations, setReservations] = useState([]);
  const [queueCount, setQueueCount] = useState(0);
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueError, setQueueError] = useState("");
  const [queueReloadKey, setQueueReloadKey] = useState(0);

  const [action, setAction] = useState(null);
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (tab !== "loans") return undefined;
    const controller = new AbortController();
    let cancelled = false;

    async function loadLoans() {
      setLoansLoading(true);
      setLoansError("");
      try {
        const data = await fetchLoans({
          status: loanStatus,
          activeOn,
          page: loanPage,
          signal: controller.signal,
        });
        if (cancelled) return;
        setLoans(data.results);
        setLoanCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setLoans([]);
        setLoanCount(0);
        setLoansError(
          getErrorMessage(requestError, "Не удалось загрузить выдачи."),
        );
      } finally {
        if (!cancelled) setLoansLoading(false);
      }
    }

    loadLoans();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [tab, loanStatus, activeOn, loanPage, loansReloadKey]);

  useEffect(() => {
    if (tab !== "queue") return undefined;
    const controller = new AbortController();
    let cancelled = false;

    async function loadQueue() {
      setQueueLoading(true);
      setQueueError("");
      try {
        const data = await fetchReservations({
          status: queueStatus,
          page: queuePage,
          signal: controller.signal,
        });
        if (cancelled) return;
        setReservations(data.results);
        setQueueCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setReservations([]);
        setQueueCount(0);
        setQueueError(
          getErrorMessage(requestError, "Не удалось загрузить очередь."),
        );
      } finally {
        if (!cancelled) setQueueLoading(false);
      }
    }

    loadQueue();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [tab, queueStatus, queuePage, queueReloadKey]);

  function switchTab(nextTab) {
    setTab(nextTab);
    setActionError("");
    setMessage("");
  }

  async function changeLoanStatus(loan, nextStatus, successText, confirmation) {
    if (confirmation && !window.confirm(confirmation)) return;

    setAction({ id: loan.id, status: nextStatus });
    setActionError("");
    setMessage("");
    try {
      await updateLoanStatus(loan.id, nextStatus);
      setMessage(successText);
      if (loans.length === 1 && loanPage > 1) setLoanPage(loanPage - 1);
      else setLoansReloadKey((value) => value + 1);
      setQueueReloadKey((value) => value + 1);
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось изменить статус брони."),
      );
    } finally {
      setAction(null);
    }
  }

  function resetLoanFilters() {
    setLoanStatus("created,active");
    setActiveOn(todayISO());
    setLoanPage(1);
  }

  const queueGroups = reservations.reduce((groups, reservation) => {
    const last = groups[groups.length - 1];
    if (last && last.book.id === reservation.book.id) {
      last.items.push(reservation);
    } else {
      groups.push({ book: reservation.book, items: [reservation] });
    }
    return groups;
  }, []);

  const loansEmpty = !loansLoading && !loansError && loans.length === 0;
  const queueEmpty = !queueLoading && !queueError && reservations.length === 0;

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Рабочее место</p>
          <h1 className="dashboard__title">Выдача и очередь</h1>
          <p className="dashboard__lead">
            Выдавайте забронированные книги, принимайте возвраты и следите за
            очередью. Возврат сразу передаёт удержание первому ожидающему.
          </p>
        </div>

        <div className="dashboard__tabs" role="tablist" aria-label="Разделы">
          <button
            type="button"
            className={`dashboard__tab${
              tab === "loans" ? " dashboard__tab--active" : ""
            }`}
            onClick={() => switchTab("loans")}
          >
            Выдачи
          </button>
          <button
            type="button"
            className={`dashboard__tab${
              tab === "queue" ? " dashboard__tab--active" : ""
            }`}
            onClick={() => switchTab("queue")}
          >
            Очередь
          </button>
        </div>

        {actionError && <ErrorMessage message={actionError} />}
        {message && (
          <p className="dashboard__success" role="status">
            {message}
          </p>
        )}

        {tab === "loans" && (
          <>
            <div className="dashboard__filters">
              <div className="field">
                <label className="field__label" htmlFor="librarian-status">
                  Статус
                </label>
                <select
                  id="librarian-status"
                  className="input"
                  value={loanStatus}
                  onChange={(event) => {
                    setLoanStatus(event.target.value);
                    setLoanPage(1);
                  }}
                >
                  {LOAN_STATUS_OPTIONS.map((option) => (
                    <option key={option.value || "all"} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label className="field__label" htmlFor="librarian-date">
                  Активны на дату
                </label>
                <input
                  id="librarian-date"
                  className="input"
                  type="date"
                  value={activeOn}
                  onChange={(event) => {
                    setActiveOn(event.target.value);
                    setLoanPage(1);
                  }}
                />
              </div>

              <button
                type="button"
                className="button button--ghost"
                onClick={resetLoanFilters}
              >
                Сбросить
              </button>
            </div>

            {loansError && (
              <ErrorMessage
                message={loansError}
                onRetry={() => setLoansReloadKey((value) => value + 1)}
              />
            )}

            {loansLoading && <Loader text="Загружаем выдачи…" />}

            {loansEmpty && (
              <section className="dashboard__empty">
                <h2 className="dashboard__empty-title">
                  На выбранную дату выдач нет
                </h2>
                <p className="dashboard__empty-text">
                  Измените дату или статус — или дождитесь новых броней читателей.
                </p>
              </section>
            )}

            {!loansLoading && !loansError && loans.length > 0 && (
              <>
                <p className="dashboard__summary">Всего броней: {loanCount}</p>

                <ul className="record-list">
                  {loans.map((loan) => (
                    <li className="record-card" key={loan.id}>
                      <div className="record-card__head">
                        <div>
                          <h2 className="record-card__title">
                            {loan.book.title}
                          </h2>
                          <p className="record-card__author">
                            {loan.book.author}
                          </p>
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
                      </dl>

                      {(loan.status === "created" ||
                        loan.status === "active") && (
                        <div className="record-card__actions">
                          {loan.status === "created" && (
                            <button
                              type="button"
                              className="button button--primary"
                              disabled={action?.id === loan.id}
                              onClick={() =>
                                changeLoanStatus(
                                  loan,
                                  "active",
                                  `Книга «${loan.book.title}» выдана.`,
                                )
                              }
                            >
                              {action?.id === loan.id &&
                              action.status === "active"
                                ? "Выдаём…"
                                : "Выдать"}
                            </button>
                          )}
                          {loan.status === "created" && (
                            <button
                              type="button"
                              className="button button--ghost"
                              disabled={action?.id === loan.id}
                              onClick={() =>
                                changeLoanStatus(
                                  loan,
                                  "cancelled",
                                  `Бронь «${loan.book.title}» снята.`,
                                  `Снять бронь на книгу «${loan.book.title}»?`,
                                )
                              }
                            >
                              {action?.id === loan.id &&
                              action.status === "cancelled"
                                ? "Снимаем…"
                                : "Снять бронь"}
                            </button>
                          )}
                          {loan.status === "active" && (
                            <button
                              type="button"
                              className="button button--ghost"
                              disabled={action?.id === loan.id}
                              onClick={() =>
                                changeLoanStatus(
                                  loan,
                                  "returned",
                                  `Возврат «${loan.book.title}» принят.`,
                                  `Принять возврат книги «${loan.book.title}»?`,
                                )
                              }
                            >
                              {action?.id === loan.id &&
                              action.status === "returned"
                                ? "Принимаем…"
                                : "Принять возврат"}
                            </button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>

                <Pagination page={loanPage} count={loanCount} onChange={setLoanPage} />
              </>
            )}
          </>
        )}

        {tab === "queue" && (
          <>
            <div className="dashboard__filters">
              <div className="field">
                <label className="field__label" htmlFor="queue-status">
                  Статус заявок
                </label>
                <select
                  id="queue-status"
                  className="input"
                  value={queueStatus}
                  onChange={(event) => {
                    setQueueStatus(event.target.value);
                    setQueuePage(1);
                  }}
                >
                  {QUEUE_STATUS_OPTIONS.map((option) => (
                    <option key={option.value || "all"} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {queueError && (
              <ErrorMessage
                message={queueError}
                onRetry={() => setQueueReloadKey((value) => value + 1)}
              />
            )}

            {queueLoading && <Loader text="Загружаем очередь…" />}

            {queueEmpty && (
              <section className="dashboard__empty">
                <h2 className="dashboard__empty-title">
                  В выбранном статусе заявок нет
                </h2>
                <p className="dashboard__empty-text">
                  Очередь появится, когда читатели начнут бронировать занятые
                  книги.
                </p>
              </section>
            )}

            {!queueLoading && !queueError && reservations.length > 0 && (
              <>
                <p className="dashboard__summary">Всего заявок: {queueCount}</p>

                {queueGroups.map((group) => (
                  <section className="queue-group" key={group.book.id}>
                    <header className="queue-group__head">
                      <h2 className="queue-group__title">
                        {group.book.title}
                      </h2>
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
                                До {formatDateTime(reservation.hold_until)}
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

                <Pagination page={queuePage} count={queueCount} onChange={setQueuePage} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
