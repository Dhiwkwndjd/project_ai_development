/** Сообщение об ошибке с необязательной кнопкой повтора. */
export default function ErrorMessage({ message, onRetry, retryLabel = "Повторить" }) {
  if (!message) return null;

  return (
    <div className="alert alert--error" role="alert">
      <span className="alert__text">{message}</span>
      {onRetry && (
        <button type="button" className="alert__retry" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}
