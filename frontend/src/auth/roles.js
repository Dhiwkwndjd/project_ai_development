/** Подписи ролей для интерфейса. */
export const ROLE_LABELS = {
  reader: "Читатель",
  librarian: "Библиотекарь",
  admin: "Администратор",
};

export function getRoleLabel(role) {
  return ROLE_LABELS[role] || role || "—";
}
