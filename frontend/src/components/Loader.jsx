/** Индикатор загрузки: строчный или на весь экран. */
export default function Loader({ text = "Загрузка…", full = false, height = "block" }) {
  const className = [
    "loader",
    full ? "loader--full" : "",
    height === "page" ? "loader--page" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className} role="status" aria-live="polite">
      <span className="loader__spinner" aria-hidden="true" />
      <span className="loader__text">{text}</span>
    </div>
  );
}
