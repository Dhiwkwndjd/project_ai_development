import { useEffect, useState } from "react";

import {
  createBook,
  createCopy,
  deleteBook,
  deleteCopy,
  fetchBook,
  fetchBooks,
  fetchCopies,
  updateBook,
  updateCopy,
} from "../../api/books";
import { getErrorMessage, getFieldErrors } from "../../api/client";
import ErrorMessage from "../ErrorMessage";
import Loader from "../Loader";
import Pagination from "../Pagination";

const CONDITION_LABELS = {
  new: "Новый",
  good: "Хороший",
  worn: "Потрёпанный",
};

const EMPTY_BOOK = {
  title: "",
  author: "",
  genre: "",
  year: "",
  description: "",
  cover_url: "",
  is_active: true,
};

const EMPTY_COPY = { inventory_number: "", condition: "good", is_active: true };

function bookValues(detail) {
  return {
    title: detail.title || "",
    author: detail.author || "",
    genre: detail.genre || "",
    year: detail.year ?? "",
    description: detail.description || "",
    cover_url: detail.cover_url || "",
    is_active: detail.is_active,
  };
}

function validateBook(values) {
  const errors = {};
  if (!values.title.trim()) errors.title = "Укажите название";
  if (!values.author.trim()) errors.author = "Укажите автора";
  if (!values.genre.trim()) errors.genre = "Укажите жанр";
  if (values.year !== "" && !Number.isInteger(Number(values.year))) {
    errors.year = "Год должен быть числом";
  }
  return errors;
}

/** Книги и экземпляры: создание, редактирование, удаление. */
export default function BooksSection() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(true);
  const [page, setPage] = useState(1);

  const [books, setBooks] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [bookForm, setBookForm] = useState(null);
  const [bookErrors, setBookErrors] = useState({});
  const [bookSaving, setBookSaving] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");

  const [copiesBook, setCopiesBook] = useState(null);
  const [copies, setCopies] = useState([]);
  const [copiesLoading, setCopiesLoading] = useState(false);
  const [copiesError, setCopiesError] = useState("");
  const [copiesReloadKey, setCopiesReloadKey] = useState(0);
  const [copyForm, setCopyForm] = useState(null);
  const [copyErrors, setCopyErrors] = useState({});
  const [copySaving, setCopySaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadBooks() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchBooks({
          search,
          includeInactive,
          page,
          signal: controller.signal,
        });
        if (cancelled) return;
        setBooks(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setBooks([]);
        setCount(0);
        setError(getErrorMessage(requestError, "Не удалось загрузить книги."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadBooks();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [search, includeInactive, page, reloadKey]);

  useEffect(() => {
    if (!copiesBook) return undefined;
    const controller = new AbortController();
    let cancelled = false;

    async function loadCopies() {
      setCopiesLoading(true);
      setCopiesError("");
      try {
        const data = await fetchCopies(copiesBook.id, {
          signal: controller.signal,
        });
        if (!cancelled) setCopies(data);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setCopies([]);
        setCopiesError(
          getErrorMessage(requestError, "Не удалось загрузить экземпляры."),
        );
      } finally {
        if (!cancelled) setCopiesLoading(false);
      }
    }

    loadCopies();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [copiesBook, copiesReloadKey]);

  function refreshBooks() {
    setReloadKey((value) => value + 1);
  }

  function refreshCopies() {
    setCopiesReloadKey((value) => value + 1);
    refreshBooks();
  }

  function handleSearch(event) {
    event.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  }

  function startCreateBook() {
    setBookForm({ mode: "create", id: null, values: { ...EMPTY_BOOK } });
    setBookErrors({});
    setActionError("");
    setMessage("");
  }

  async function startEditBook(book) {
    setBookErrors({});
    setActionError("");
    setMessage("");
    setActionId(book.id);
    try {
      const detail = await fetchBook(book.id);
      setBookForm({
        mode: "edit",
        id: book.id,
        values: bookValues(detail),
      });
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось открыть книгу."),
      );
    } finally {
      setActionId(null);
    }
  }

  function updateBookField(field, value) {
    setBookForm((current) => ({
      ...current,
      values: { ...current.values, [field]: value },
    }));
    setBookErrors((current) => ({ ...current, [field]: "" }));
  }

  async function saveBook(event) {
    event.preventDefault();
    setActionError("");
    setMessage("");

    const errors = validateBook(bookForm.values);
    if (Object.keys(errors).length) {
      setBookErrors(errors);
      return;
    }

    const payload = {
      ...bookForm.values,
      title: bookForm.values.title.trim(),
      author: bookForm.values.author.trim(),
      genre: bookForm.values.genre.trim(),
      year: bookForm.values.year === "" ? null : Number(bookForm.values.year),
    };

    setBookSaving(true);
    try {
      const saved =
        bookForm.mode === "create"
          ? await createBook(payload)
          : await updateBook(bookForm.id, payload);
      setMessage(
        bookForm.mode === "create"
          ? `Книга «${saved.title}» добавлена.`
          : `Книга «${saved.title}» сохранена.`,
      );
      setBookForm(null);
      if (bookForm.mode === "create") setPage(1);
      refreshBooks();
    } catch (requestError) {
      setBookErrors(getFieldErrors(requestError));
      setActionError(getErrorMessage(requestError, "Не удалось сохранить книгу."));
    } finally {
      setBookSaving(false);
    }
  }

  async function removeBook(book) {
    const confirmed = window.confirm(
      `Удалить книгу «${book.title}»? Действие необратимо.`,
    );
    if (!confirmed) return;

    setActionId(book.id);
    setActionError("");
    setMessage("");
    try {
      await deleteBook(book.id);
      setMessage(`Книга «${book.title}» удалена.`);
      if (copiesBook?.id === book.id) setCopiesBook(null);
      refreshBooks();
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось удалить книгу."),
      );
    } finally {
      setActionId(null);
    }
  }

  function selectCopiesBook(book) {
    setCopiesBook(book);
    setCopyForm(null);
    setCopyErrors({});
  }

  function startCreateCopy() {
    setCopyForm({ mode: "create", id: null, values: { ...EMPTY_COPY } });
    setCopyErrors({});
  }

  function startEditCopy(copy) {
    setCopyForm({
      mode: "edit",
      id: copy.id,
      values: {
        inventory_number: copy.inventory_number,
        condition: copy.condition,
        is_active: copy.is_active,
      },
    });
    setCopyErrors({});
  }

  function updateCopyField(field, value) {
    setCopyForm((current) => ({
      ...current,
      values: { ...current.values, [field]: value },
    }));
    setCopyErrors((current) => ({ ...current, [field]: "" }));
  }

  async function saveCopy(event) {
    event.preventDefault();
    setActionError("");
    setMessage("");

    if (!copyForm.values.inventory_number.trim()) {
      setCopyErrors({ inventory_number: "Укажите инвентарный номер" });
      return;
    }

    const payload = {
      ...copyForm.values,
      inventory_number: copyForm.values.inventory_number.trim(),
    };

    setCopySaving(true);
    try {
      if (copyForm.mode === "create") {
        await createCopy(copiesBook.id, payload);
      } else {
        await updateCopy(copiesBook.id, copyForm.id, payload);
      }
      setMessage(
        copyForm.mode === "create"
          ? "Экземпляр добавлен."
          : "Экземпляр сохранён.",
      );
      setCopyForm(null);
      refreshCopies();
    } catch (requestError) {
      setCopyErrors(getFieldErrors(requestError));
      setActionError(
        getErrorMessage(requestError, "Не удалось сохранить экземпляр."),
      );
    } finally {
      setCopySaving(false);
    }
  }

  async function removeCopy(copy) {
    const confirmed = window.confirm(
      `Удалить экземпляр «${copy.inventory_number}»?`,
    );
    if (!confirmed) return;

    setActionId(copy.id);
    setActionError("");
    setMessage("");
    try {
      await deleteCopy(copiesBook.id, copy.id);
      setMessage(`Экземпляр «${copy.inventory_number}» удалён.`);
      refreshCopies();
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось удалить экземпляр."),
      );
    } finally {
      setActionId(null);
    }
  }

  const isEmpty = !loading && !error && books.length === 0;

  return (
    <section>
      <div className="admin-toolbar">
        <form className="admin-filters" onSubmit={handleSearch}>
          <div className="field">
            <label className="field__label" htmlFor="admin-book-search">
              Поиск
            </label>
            <input
              id="admin-book-search"
              className="input"
              type="search"
              placeholder="Название или автор"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <label className="admin-check">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => {
                setIncludeInactive(event.target.checked);
                setPage(1);
              }}
            />
            Показывать снятые с каталога
          </label>

          <button className="button button--primary" type="submit">
            Найти
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={() => {
              setSearchInput("");
              setSearch("");
              setPage(1);
            }}
          >
            Сбросить
          </button>
        </form>

        <button
          type="button"
          className="button button--primary"
          onClick={startCreateBook}
        >
          Добавить книгу
        </button>
      </div>

      {bookForm && (
        <form className="admin-panel admin-form" onSubmit={saveBook}>
          <h2 className="admin-panel__title">
            {bookForm.mode === "create" ? "Новая книга" : "Редактирование книги"}
          </h2>

          <div className="admin-form__grid">
            <div className="field">
              <label className="field__label" htmlFor="admin-book-title">
                Название
              </label>
              <input
                id="admin-book-title"
                className={`input${bookErrors.title ? " input--invalid" : ""}`}
                value={bookForm.values.title}
                onChange={(event) =>
                  updateBookField("title", event.target.value)
                }
              />
              {bookErrors.title && (
                <span className="field__error">{bookErrors.title}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-book-author">
                Автор
              </label>
              <input
                id="admin-book-author"
                className={`input${
                  bookErrors.author ? " input--invalid" : ""
                }`}
                value={bookForm.values.author}
                onChange={(event) =>
                  updateBookField("author", event.target.value)
                }
              />
              {bookErrors.author && (
                <span className="field__error">{bookErrors.author}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-book-genre">
                Жанр
              </label>
              <input
                id="admin-book-genre"
                className={`input${bookErrors.genre ? " input--invalid" : ""}`}
                value={bookForm.values.genre}
                onChange={(event) =>
                  updateBookField("genre", event.target.value)
                }
              />
              {bookErrors.genre && (
                <span className="field__error">{bookErrors.genre}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-book-year">
                Год издания
              </label>
              <input
                id="admin-book-year"
                className={`input${bookErrors.year ? " input--invalid" : ""}`}
                type="number"
                min="0"
                max="2100"
                value={bookForm.values.year}
                onChange={(event) =>
                  updateBookField("year", event.target.value)
                }
              />
              {bookErrors.year && (
                <span className="field__error">{bookErrors.year}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-book-cover">
                Обложка (URL)
              </label>
              <input
                id="admin-book-cover"
                className={`input${
                  bookErrors.cover_url ? " input--invalid" : ""
                }`}
                value={bookForm.values.cover_url}
                onChange={(event) =>
                  updateBookField("cover_url", event.target.value)
                }
              />
              {bookErrors.cover_url && (
                <span className="field__error">{bookErrors.cover_url}</span>
              )}
            </div>

            <label className="admin-check">
              <input
                type="checkbox"
                checked={bookForm.values.is_active}
                onChange={(event) =>
                  updateBookField("is_active", event.target.checked)
                }
              />
              В каталоге
            </label>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="admin-book-description">
              Описание
            </label>
            <textarea
              id="admin-book-description"
              className="input admin-textarea"
              rows="3"
              value={bookForm.values.description}
              onChange={(event) =>
                updateBookField("description", event.target.value)
              }
            />
          </div>

          <div className="admin-form__actions">
            <button
              className="button button--primary"
              type="submit"
              disabled={bookSaving}
            >
              {bookSaving ? "Сохраняем…" : "Сохранить"}
            </button>
            <button
              className="button button--ghost"
              type="button"
              onClick={() => setBookForm(null)}
              disabled={bookSaving}
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {actionError && <ErrorMessage message={actionError} />}
      {message && (
        <p className="dashboard__success" role="status">
          {message}
        </p>
      )}

      {error && (
        <ErrorMessage
          message={error}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      )}

      {loading && <Loader text="Загружаем книги…" />}

      {isEmpty && (
        <section className="dashboard__empty">
          <h2 className="dashboard__empty-title">Книги не найдены</h2>
          <p className="dashboard__empty-text">
            Измените поиск или добавьте новую книгу в фонд.
          </p>
          <button
            type="button"
            className="button button--primary"
            onClick={startCreateBook}
          >
            Добавить книгу
          </button>
        </section>
      )}

      {!loading && !error && books.length > 0 && (
        <>
          <p className="dashboard__summary">Всего книг: {count}</p>

          <ul className="admin-list">
            {books.map((book) => {
              const busy = actionId === book.id;
              return (
                <li className="admin-row" key={book.id}>
                  <div className="admin-row__main">
                    <span className="admin-row__title">{book.title}</span>
                    <span className="admin-row__meta">
                      {book.author}
                      {book.year ? ` · ${book.year}` : ""} · {book.genre}
                    </span>
                    <span className="admin-row__meta">
                      Экземпляров: {book.total_copies}, свободно:{" "}
                      {book.free_copies}
                    </span>
                  </div>

                  <div className="admin-row__side">
                    <span
                      className={`status ${
                        book.is_active ? "status--active" : "status--cancelled"
                      }`}
                    >
                      {book.is_active ? "В каталоге" : "Снята"}
                    </span>

                    <div className="admin-row__actions">
                      <button
                        type="button"
                        className="button button--ghost admin-row__button"
                        onClick={() => selectCopiesBook(book)}
                      >
                        Экземпляры
                      </button>
                      <button
                        type="button"
                        className="button button--ghost admin-row__button"
                        disabled={busy}
                        onClick={() => startEditBook(book)}
                      >
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="button button--ghost admin-row__button admin-row__button--danger"
                        disabled={busy}
                        onClick={() => removeBook(book)}
                      >
                        Удалить
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>

          <Pagination page={page} count={count} onChange={setPage} />
        </>
      )}

      {copiesBook && (
        <section className="admin-panel admin-copies">
          <div className="admin-panel__head">
            <h2 className="admin-panel__title">
              Экземпляры «{copiesBook.title}»
            </h2>
            <div className="admin-panel__actions">
              <button
                type="button"
                className="button button--primary"
                onClick={startCreateCopy}
              >
                Добавить экземпляр
              </button>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => {
                  setCopiesBook(null);
                  setCopyForm(null);
                }}
              >
                Закрыть
              </button>
            </div>
          </div>

          {copyForm && (
            <form className="admin-copy-form" onSubmit={saveCopy}>
              <div className="field">
                <label className="field__label" htmlFor="admin-copy-number">
                  Инвентарный номер
                </label>
                <input
                  id="admin-copy-number"
                  className={`input${
                    copyErrors.inventory_number ? " input--invalid" : ""
                  }`}
                  value={copyForm.values.inventory_number}
                  onChange={(event) =>
                    updateCopyField("inventory_number", event.target.value)
                  }
                />
                {copyErrors.inventory_number && (
                  <span className="field__error">
                    {copyErrors.inventory_number}
                  </span>
                )}
              </div>

              <div className="field">
                <label className="field__label" htmlFor="admin-copy-condition">
                  Состояние
                </label>
                <select
                  id="admin-copy-condition"
                  className="input"
                  value={copyForm.values.condition}
                  onChange={(event) =>
                    updateCopyField("condition", event.target.value)
                  }
                >
                  {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <label className="admin-check">
                <input
                  type="checkbox"
                  checked={copyForm.values.is_active}
                  onChange={(event) =>
                    updateCopyField("is_active", event.target.checked)
                  }
                />
                Доступен
              </label>

              <div className="admin-form__actions">
                <button
                  className="button button--primary"
                  type="submit"
                  disabled={copySaving}
                >
                  {copySaving ? "Сохраняем…" : "Сохранить"}
                </button>
                <button
                  className="button button--ghost"
                  type="button"
                  onClick={() => setCopyForm(null)}
                  disabled={copySaving}
                >
                  Отмена
                </button>
              </div>
            </form>
          )}

          {copiesError && (
            <ErrorMessage
              message={copiesError}
              onRetry={() => setCopiesReloadKey((value) => value + 1)}
            />
          )}

          {copiesLoading && <Loader text="Загружаем экземпляры…" />}

          {!copiesLoading && !copiesError && copies.length === 0 && (
            <p className="admin-empty-text">
              У книги пока нет экземпляров. Добавьте первый.
            </p>
          )}

          {!copiesLoading && !copiesError && copies.length > 0 && (
            <ul className="admin-copy-list">
              {copies.map((copy) => {
                const busy = actionId === copy.id;
                return (
                  <li className="admin-copy-row" key={copy.id}>
                    <span className="admin-copy-row__number">
                      {copy.inventory_number}
                    </span>
                    <span className="admin-row__meta">
                      {CONDITION_LABELS[copy.condition] || copy.condition}
                    </span>
                    <span
                      className={`status ${
                        copy.is_active
                          ? "status--active"
                          : "status--cancelled"
                      }`}
                    >
                      {copy.is_active ? "Доступен" : "Списан"}
                    </span>
                    <div className="admin-copy-row__actions">
                      <button
                        type="button"
                        className="button button--ghost admin-row__button"
                        disabled={busy}
                        onClick={() => startEditCopy(copy)}
                      >
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="button button--ghost admin-row__button admin-row__button--danger"
                        disabled={busy}
                        onClick={() => removeCopy(copy)}
                      >
                        Удалить
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </section>
  );
}
