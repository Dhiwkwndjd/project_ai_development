import { api } from "./client";

/** Встать в очередь на книгу. */
export async function createReservation(bookId) {
  const { data } = await api.post("/reservations/", { book_id: bookId });
  return data;
}

/** Мои заявки и позиция в очереди. */
export async function fetchMyReservations({ status = "", page = 1, signal } = {}) {
  const params = { page };
  if (status) params.status = status;

  const { data } = await api.get("/reservations/my/", { params, signal });
  return data;
}

/** Все заявки для библиотекаря: фильтр по книге и статусу. */
export async function fetchReservations({
  bookId = null,
  status = "",
  page = 1,
  signal,
} = {}) {
  const params = { page };
  if (bookId) params.book_id = bookId;
  if (status) params.status = status;

  const { data } = await api.get("/reservations/", { params, signal });
  return data;
}

/** Отменить свою заявку. */
export async function cancelReservation(reservationId) {
  await api.delete(`/reservations/${reservationId}/`);
}
