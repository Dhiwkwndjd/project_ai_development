import { api } from "./client";

/** Пользователи для админ-панели: поиск, роль, статус, пагинация. */
export async function fetchUsers({
  search = "",
  role = "",
  isActive = null,
  page = 1,
  signal,
} = {}) {
  const params = { page };
  if (search) params.search = search;
  if (role) params.role = role;
  if (isActive !== null) params.is_active = String(isActive);

  const { data } = await api.get("/admin/users/", { params, signal });
  return data;
}

/** Создать библиотекаря. Роль назначает backend. */
export async function createLibrarian(payload) {
  const { data } = await api.post("/admin/users/", payload);
  return data;
}

/** Сменить роль пользователя. */
export async function updateUserRole(userId, role) {
  const { data } = await api.patch(`/admin/users/${userId}/role/`, { role });
  return data;
}

/** Заблокировать (false) или разблокировать (true) пользователя. */
export async function updateUserStatus(userId, isActive) {
  const { data } = await api.patch(`/admin/users/${userId}/status/`, {
    is_active: isActive,
  });
  return data;
}
