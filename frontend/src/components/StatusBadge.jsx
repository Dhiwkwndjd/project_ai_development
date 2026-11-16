const LOAN_LABELS = {
  created: "Забронирована",
  active: "Выдана",
  returned: "Возвращена",
  cancelled: "Отменена",
};

const RESERVATION_LABELS = {
  waiting: "Ожидает",
  ready: "Готова к выдаче",
  fulfilled: "Выполнена",
  cancelled: "Отменена",
  expired: "Просрочена",
};

/** Статус брони или заявки в очереди. */
export default function StatusBadge({ status, kind = "loan" }) {
  const labels = kind === "reservation" ? RESERVATION_LABELS : LOAN_LABELS;
  return (
    <span className={`status status--${status}`}>
      {labels[status] || status}
    </span>
  );
}
