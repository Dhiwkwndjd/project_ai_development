import { api } from "./client";

/** Размер страницы задан на backend (`PAGE_SIZE = 9`). */
export const PAGE_SIZE = 9;

/** Список книг с поиском, фильтром и пагинацией. */
export async function fetchBooks({
  search = "",
  genre = "",
  includeInactive = false,
  page = 1,
  signal,
} = {}) {
  const params = { page };
  if (search) params.search = search;
  if (genre) params.genre = genre;
  if (includeInactive) params.include_inactive = "true";

  const { data } = await api.get("/books/", { params, signal });
  return data;
}

/** Жанры для выпадающего фильтра. */
export async function fetchGenres({ signal } = {}) {
  const { data } = await api.get("/books/genres/", { signal });
  return data.genres;
}

/** Подробная карточка книги. */
export async function fetchBook(bookId, { signal } = {}) {
  const { data } = await api.get(`/books/${bookId}/`, { signal });
  return data;
}

/** Свободные экземпляры книги на выбранный интервал. */
export async function fetchAvailability(bookId, { startDate = "", dueDate = "", signal } = {}) {
  const params = {};
  if (startDate) params.start_date = startDate;
  if (dueDate) params.due_date = dueDate;

  const { data } = await api.get(`/books/${bookId}/availability/`, { params, signal });
  return data;
}

/** Создать книгу (администратор). */
export async function createBook(payload) {
  const { data } = await api.post("/books/", payload);
  return data;
}

/** Изменить книгу или снять её с каталога (администратор). */
export async function updateBook(bookId, payload) {
  const { data } = await api.patch(`/books/${bookId}/`, payload);
  return data;
}

/** Удалить книгу без истории броней (администратор). */
export async function deleteBook(bookId) {
  await api.delete(`/books/${bookId}/`);
}

/** Экземпляры книги (администратор). */
export async function fetchCopies(bookId, { signal } = {}) {
  const { data } = await api.get(`/books/${bookId}/copies/`, { signal });
  return data;
}

/** Добавить экземпляр книги (администратор). */
export async function createCopy(bookId, payload) {
  const { data } = await api.post(`/books/${bookId}/copies/`, payload);
  return data;
}

/** Изменить экземпляр: состояние, номер, доступность (администратор). */
export async function updateCopy(bookId, copyId, payload) {
  const { data } = await api.patch(`/books/${bookId}/copies/${copyId}/`, payload);
  return data;
}

/** Удалить экземпляр без истории броней (администратор). */
export async function deleteCopy(bookId, copyId) {
  await api.delete(`/books/${bookId}/copies/${copyId}/`);
}
