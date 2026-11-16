import { api } from "./client";

/** Журнал действий с фильтрами и серверной пагинацией. */
export async function fetchLogs({
  userId = "",
  userEmail = "",
  action = "",
  dateFrom = "",
  dateTo = "",
  page = 1,
  signal,
} = {}) {
  const params = { page };
  if (userId) params.user_id = userId;
  if (userEmail) params.user_email = userEmail;
  if (action) params.action = action;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const { data } = await api.get("/logs/", { params, signal });
  return data;
}
