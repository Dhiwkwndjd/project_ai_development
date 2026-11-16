import { useState } from "react";

/** Обложка книги с запасным вариантом, если картинка не загрузилась. */
export default function BookCover({ book, large = false }) {
  const [failedUrl, setFailedUrl] = useState("");
  const failed = failedUrl === book.cover_url;

  const className = `book-cover${large ? " book-cover--large" : ""}`;
  const letter = (book.title || "?").trim().charAt(0).toUpperCase() || "?";

  if (!book.cover_url || failed) {
    return (
      <div className={`${className} book-cover--fallback`} aria-hidden="true">
        <span className="book-cover__letter">{letter}</span>
      </div>
    );
  }

  return (
    <div className={className}>
      <img
        className="book-cover__image"
        src={book.cover_url}
        alt={`Обложка книги «${book.title}»`}
        loading="lazy"
        onError={() => setFailedUrl(book.cover_url)}
      />
    </div>
  );
}
