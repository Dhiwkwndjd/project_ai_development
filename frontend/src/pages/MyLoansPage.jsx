import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "../api/client";
import { fetchLoans, updateLoanStatus } from "../api/loans";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import Pagination from "../components/Pagination";
import SiteHeader from "../components/SiteHeader";
import StatusBadge from "../components/StatusBadge";
import { formatDate } from "../utils/dates";
import "../styles/dashboard.css";

const STATUS_TABS = [
  { value: "", label: "Все" },
  { value: "created", label: "Забронированы" },
  { value: "active", label: "На руках" },
  { value: "returned", label: "Возвращены" },
  { value: "cancelled", label: "Отменены" },
];

export default function MyLoansPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [loans, setLoans] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionId, setActionId] = useState(null);
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
          getErrorMessage(requestError, "Не удалось загрузить брони. Попробуйте ещё раз."),
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
  }, [status, page, reloadKey]);

  function changeStatus(value) {
    setStatus(value);
    setPage(1);
    setActionError("");
  }

  async function cancelLoan(loan) {
    if (!window.confirm(`Отменить бронь «${loan.book.title}»?`)) return;

    setActionId(loan.id);
    setActionError("");
    try {
      await updateLoanStatus(loan.id, "cancelled");
      if (loans.length === 1 && page > 1) setPage(page - 1);
      else setReloadKey((value) => value + 1);
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось отменить бронь. Попробуйте ещё раз."),
      );
    } finally {
      setActionId(null);
    }
  }

  const isEmpty = !loading && !error && loans.length === 0;

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Личный кабинет</p>
          <h1 className="dashboard__title">Мои брони</h1>
          <p className="dashboard__lead">
            Здесь видны ваши брони и выдачи. Бронь можно отменить, пока
            библиотекарь не выдал книгу.
          </p>
        </div>

        <div className="dashboard__tabs" role="tablist" aria-label="Статусы броней">
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

        {loading && <Loader text="Загружаем ваши брони…" />}

        {isEmpty && (
          <section className="dashboard__empty">
            <h2 className="dashboard__empty-title">
              {status ? "В этом статусе броней нет" : "У вас пока нет броней"}
            </h2>
            <p className="dashboard__empty-text">
              {status
                ? "Выберите другой статус или посмотрите весь список."
                : "Найдите книгу в каталоге и оформите бронь или встаньте в очередь."}
            </p>
            <Link className="button button--primary" to="/catalog">
              Перейти в каталог
            </Link>
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
                      <dt>Экземпляр</dt>
                      <dd>{loan.copy.inventory_number}</dd>
                    </div>
                    <div className="record-card__detail">
                      <dt>Период</dt>
                      <dd>
                        {formatDate(loan.start_date)} — {formatDate(loan.due_date)}
                      </dd>
                    </div>
                    <div className="record-card__detail">
                      <dt>Создана</dt>
                      <dd>{formatDate(loan.created_at.slice(0, 10))}</dd>
                    </div>
                  </dl>

                  {loan.comment && (
                    <p className="record-card__comment">{loan.comment}</p>
                  )}

                  {loan.status === "created" && (
                    <div className="record-card__actions">
                      <button
                        type="button"
                        className="button button--ghost"
                        disabled={actionId === loan.id}
                        onClick={() => cancelLoan(loan)}
                      >
                        {actionId === loan.id ? "Отменяем…" : "Отменить бронь"}
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
