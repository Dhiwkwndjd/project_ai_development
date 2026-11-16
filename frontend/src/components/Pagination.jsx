import { PAGE_SIZE } from "../api/books";

/** Постраничная навигация каталога. */
export default function Pagination({ page, count, onChange }) {
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  if (totalPages <= 1) return null;

  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);

  return (
    <nav className="pagination" aria-label="Страницы каталога">
      <button
        type="button"
        className="button button--ghost pagination__button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
      >
        Назад
      </button>

      <div className="pagination__pages">
        {pages.map((number) => (
          <button
            key={number}
            type="button"
            className={`pagination__page${number === page ? " pagination__page--active" : ""}`}
            onClick={() => onChange(number)}
            disabled={number === page}
            aria-current={number === page ? "page" : undefined}
          >
            {number}
          </button>
        ))}
      </div>

      <button
        type="button"
        className="button button--ghost pagination__button"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
      >
        Вперёд
      </button>
    </nav>
  );
}
