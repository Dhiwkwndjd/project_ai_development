import { api } from "./client";

/** Создать бронь на экземпляр или на свободный экземпляр книги. */
export async function createLoan({
  copyId = null,
  bookId = null,
  startDate = "",
  dueDate = "",
  comment = "",
} = {}) {
  const payload = {};
  if (copyId) payload.copy_id = copyId;
  if (bookId) payload.book_id = bookId;
  if (startDate) payload.start_date = startDate;
  if (dueDate) payload.due_date = dueDate;
  if (comment) payload.comment = comment;

  const { data } = await api.post("/loans/", payload);
  return data;
}

/** Список броней с фильтрами и серверной пагинацией. */
export async function fetchLoans({
  status = "",
  bookId = null,
  readerId = null,
  activeOn = "",
  dateFrom = "",
  dateTo = "",
  page = 1,
  signal,
} = {}) {
  const params = { page };
  if (status) params.status = status;
  if (bookId) params.book_id = bookId;
  if (readerId) params.reader_id = readerId;
  if (activeOn) params.active_on = activeOn;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const { data } = await api.get("/loans/", { params, signal });
  return data;
}

/** Сменить статус брони: выдать, вернуть или отменить. */
export async function updateLoanStatus(loanId, status) {
  const { data } = await api.patch(`/loans/${loanId}/status/`, { status });
  return data;
}
