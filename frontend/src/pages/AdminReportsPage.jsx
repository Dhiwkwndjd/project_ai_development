import { useEffect, useState } from "react";

import { getErrorMessage } from "../api/client";
import { downloadReportCsv, fetchReportSummary } from "../api/reports";
import AdminNav from "../components/admin/AdminNav";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import SiteHeader from "../components/SiteHeader";
import { addDays, formatDate, todayISO } from "../utils/dates";
import "../styles/dashboard.css";
import "../styles/admin.css";

const DEFAULT_FROM = () => addDays(todayISO(), -30);
const DEFAULT_TO = () => todayISO();

/** Отчёт за период: сводка, топ книг, загрузка фонда и CSV. */
export default function AdminReportsPage() {
  const [dateFrom, setDateFrom] = useState(DEFAULT_FROM);
  const [dateTo, setDateTo] = useState(DEFAULT_TO);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [exporting, setExporting] = useState("");
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadSummary() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchReportSummary({
          dateFrom,
          dateTo,
          signal: controller.signal,
        });
        if (!cancelled) setSummary(data);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setSummary(null);
        setError(getErrorMessage(requestError, "Не удалось загрузить отчёт."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSummary();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [dateFrom, dateTo, reloadKey]);

  async function handleExport(kind) {
    setExporting(kind);
    setExportError("");
    try {
      const period = kind === "loans" ? { dateFrom, dateTo } : {};
      await downloadReportCsv(kind, period);
    } catch (requestError) {
      setExportError(getErrorMessage(requestError, "Не удалось скачать CSV."));
    } finally {
      setExporting("");
    }
  }

  function resetPeriod() {
    setDateFrom(DEFAULT_FROM());
    setDateTo(DEFAULT_TO());
  }

  const totals = summary?.totals;
  const cards = totals
    ? [
        { label: "Выдачи", value: totals.issued },
        { label: "Возвраты", value: totals.returned },
        { label: "Отмены", value: totals.cancelled },
        { label: "Заявки в очередь", value: totals.reservations },
      ]
    : [];

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard admin">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Администрирование</p>
          <h1 className="dashboard__title">Отчёты</h1>
          <p className="dashboard__lead">
            Выдачи, возвраты, отмены и очередь за период, рейтинг книг и
            загрузка экземпляров. Цифры считает SQL-агрегация.
          </p>
        </div>

        <AdminNav />

        <div className="admin-filters">
          <div className="field">
            <label className="field__label" htmlFor="report-date-from">
              Период с
            </label>
            <input
              id="report-date-from"
              className="input"
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="report-date-to">
              Период по
            </label>
            <input
              id="report-date-to"
              className="input"
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </div>

          <button
            type="button"
            className="button button--ghost"
            onClick={resetPeriod}
          >
            Последние 30 дней
          </button>

          <button
            type="button"
            className="button"
            onClick={() => handleExport("loans")}
            disabled={exporting === "loans"}
          >
            {exporting === "loans" ? "Готовим…" : "Экспорт loans.csv"}
          </button>

          <button
            type="button"
            className="button button--ghost"
            onClick={() => handleExport("books")}
            disabled={exporting === "books"}
          >
            {exporting === "books" ? "Готовим…" : "Экспорт books.csv"}
          </button>
        </div>

        {exportError && <ErrorMessage message={exportError} />}

        {error && (
          <ErrorMessage
            message={error}
            onRetry={() => setReloadKey((value) => value + 1)}
          />
        )}

        {loading && <Loader text="Считаем отчёт…" />}

        {!loading && !error && summary && (
          <>
            <p className="dashboard__summary">
              Период: {formatDate(dateFrom) || "начало"} —{" "}
              {formatDate(dateTo) || "сегодня"}
            </p>

            <div className="stat-grid">
              {cards.map((card) => (
                <article className="stat-card" key={card.label}>
                  <span className="stat-card__value">{card.value}</span>
                  <span className="stat-card__label">{card.label}</span>
                </article>
              ))}
            </div>

            <section className="admin-panel">
              <header className="admin-panel__head">
                <h2 className="admin-panel__title">Самые популярные книги</h2>
              </header>

              {summary.top_books.length === 0 ? (
                <p className="admin-empty-text">
                  За выбранный период выдач не было.
                </p>
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Книга</th>
                        <th>Автор</th>
                        <th className="admin-table__number">Броней</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.top_books.map((book, index) => (
                        <tr key={book.book_id}>
                          <td>{index + 1}</td>
                          <td>{book.title}</td>
                          <td>{book.author}</td>
                          <td className="admin-table__number">
                            {book.loans_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="admin-panel">
              <header className="admin-panel__head">
                <h2 className="admin-panel__title">Загрузка экземпляров</h2>
              </header>

              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Книга</th>
                      <th>Автор</th>
                      <th className="admin-table__number">Экземпляров</th>
                      <th className="admin-table__number">Задействовано</th>
                      <th className="admin-table__number">Броней</th>
                      <th className="admin-table__number">Загрузка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.book_load.map((book) => (
                      <tr key={book.book_id}>
                        <td>{book.title}</td>
                        <td>{book.author}</td>
                        <td className="admin-table__number">
                          {book.copies_total}
                        </td>
                        <td className="admin-table__number">
                          {book.copies_used}
                        </td>
                        <td className="admin-table__number">
                          {book.loans_count}
                        </td>
                        <td className="admin-table__number">
                          {book.load_percent}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
