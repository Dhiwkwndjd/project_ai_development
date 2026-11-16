/** Доступность книги: сколько экземпляров свободно. */
export default function AvailabilityBadge({ free, total }) {
  let modifier = "availability--free";
  let label = `Свободно ${free} из ${total}`;

  if (!total) {
    modifier = "availability--none";
    label = "Экземпляров нет";
  } else if (!free) {
    modifier = "availability--busy";
    label = "Нет свободных экземпляров";
  }

  return (
    <span className={`availability ${modifier}`}>
      <span className="availability__dot" aria-hidden="true" />
      {label}
    </span>
  );
}
