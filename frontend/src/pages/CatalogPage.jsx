import { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { fetchBooks, fetchGenres } from "../api/books";
import { getErrorMessage } from "../api/client";
import AvailabilityBadge from "../components/AvailabilityBadge";
import BookCover from "../components/BookCover";
import ErrorMessage from "../components/ErrorMessage";
import Loader from "../components/Loader";
import Pagination from "../components/Pagination";
import SiteHeader from "../components/SiteHeader";
import "../styles/catalog.css";

function parsePage(raw) {
  const page = Number.parseInt(raw || "1", 10);
  return Number.isFinite(page) && page > 0 ? page : 1;
}

export default function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const catalogPath = `${location.pathname}${location.search}`;
  const search = searchParams.get("search") || "";
  const genre = searchParams.get("genre") || "";
  const page = parsePage(searchParams.get("page"));

  const [searchInput, setSearchInput] = useState(search);
  const [lastSearch, setLastSearch] = useState(search);
  const [genres, setGenres] = useState([]);
  const [books, setBooks] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // Возврат по истории браузера обновляет поле поиска во время рендера.
  if (search !== lastSearch) {
    setLastSearch(search);
    setSearchInput(search);
  }

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    fetchGenres({ signal: controller.signal })
      .then((items) => {
        if (!cancelled) setGenres(items);
      })
      .catch(() => {
        // Без списка жанров фильтр остаётся, но пустым — каталог работает.
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadBooks() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchBooks({ search, genre, page, signal: controller.signal });
        if (cancelled) return;
        setBooks(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setBooks([]);
        setCount(0);
        setError(
          getErrorMessage(requestError, "Не удалось загрузить каталог. Попробуйте ещё раз."),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadBooks();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [search, genre, page, reloadKey]);

  function updateFilters(patch) {
    const next = new URLSearchParams(searchParams);
    Object.entries(patch).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    next.delete("page");
    setSearchParams(next);
  }

  function handleSearch(event) {
    event.preventDefault();
    updateFilters({ search: searchInput.trim() });
  }

  function handleGenre(event) {
    updateFilters({ genre: event.target.value });
  }

  function resetFilters() {
    setSearchInput("");
    setSearchParams({});
  }

  function goToPage(nextPage) {
    const next = new URLSearchParams(searchParams);
    if (nextPage <= 1) next.delete("page");
    else next.set("page", String(nextPage));
    setSearchParams(next);
  }

  const hasFilters = Boolean(search || genre);
  const isEmpty = !loading && !error && books.length === 0;

  return (
    <div className="page">
      <SiteHeader />

      <main className="catalog">
        <div className="catalog__head">
          <p className="catalog__eyebrow">Фонд библиотеки</p>
          <h1 className="catalog__title">Каталог книг</h1>
          <p className="catalog__lead">
            Найдите книгу по названию или автору и проверьте, сколько экземпляров
            свободно.
          </p>
        </div>

        <form className="catalog__filters" onSubmit={handleSearch}>
          <div className="field catalog__search">
            <label className="field__label" htmlFor="catalog-search">
              Поиск
            </label>
            <input
              id="catalog-search"
              className="input"
              type="search"
              placeholder="Название или автор"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <div className="field catalog__genre">
            <label className="field__label" htmlFor="catalog-genre">
              Жанр
            </label>
            <select
              id="catalog-genre"
              className="input"
              value={genre}
              onChange={handleGenre}
            >
              <option value="">Все жанры</option>
              {genres.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <button className="button button--primary" type="submit">
            Найти
          </button>

          {hasFilters && (
            <button
              className="button button--ghost"
              type="button"
              onClick={resetFilters}
            >
              Сбросить
            </button>
          )}
        </form>

        {error && (
          <ErrorMessage
            message={error}
            onRetry={() => setReloadKey((value) => value + 1)}
          />
        )}

        {loading && <Loader text="Загружаем каталог…" />}

        {isEmpty && (
          <section className="catalog__empty">
            <h2 className="catalog__empty-title">
              {hasFilters ? "Ничего не найдено" : "Каталог пока пуст"}
            </h2>
            <p className="catalog__empty-text">
              {hasFilters
                ? "Попробуйте изменить запрос или выбрать другой жанр."
                : "Книги появятся здесь, когда администратор добавит их в фонд."}
            </p>
            {hasFilters && (
              <button
                className="button button--ghost"
                type="button"
                onClick={resetFilters}
              >
                Сбросить фильтры
              </button>
            )}
          </section>
        )}

        {!loading && !error && books.length > 0 && (
          <>
            <p className="catalog__summary">Найдено книг: {count}</p>

            <ul className="catalog__grid">
              {books.map((book) => (
                <li className="catalog__item" key={book.id}>
                  <Link
                    className="book-card"
                    to={`/books/${book.id}`}
                    state={{ from: catalogPath }}
                  >
                    <BookCover book={book} />
                    <div className="book-card__body">
                      <div className="book-card__top">
                        <span className="book-card__genre">{book.genre}</span>
                        {book.year ? (
                          <span className="book-card__year">{book.year}</span>
                        ) : null}
                      </div>
                      <h2 className="book-card__title">{book.title}</h2>
                      <p className="book-card__author">{book.author}</p>
                      <div className="book-card__footer">
                        <AvailabilityBadge
                          free={book.free_copies}
                          total={book.total_copies}
                        />
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>

            <Pagination page={page} count={count} onChange={goToPage} />
          </>
        )}
      </main>
    </div>
  );
}
