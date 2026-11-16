import { useEffect, useState } from "react";

import {
  createLibrarian,
  fetchUsers,
  updateUserRole,
  updateUserStatus,
} from "../../api/admin";
import { getErrorMessage, getFieldErrors } from "../../api/client";
import { getRoleLabel } from "../../auth/roles";
import { useAuth } from "../../auth/context";
import ErrorMessage from "../ErrorMessage";
import Loader from "../Loader";
import Pagination from "../Pagination";
import { formatDateTime } from "../../utils/dates";

const ROLE_OPTIONS = [
  { value: "reader", label: "Читатель" },
  { value: "librarian", label: "Библиотекарь" },
  { value: "admin", label: "Администратор" },
];

const STATUS_OPTIONS = [
  { value: "", label: "Все" },
  { value: "true", label: "Активные" },
  { value: "false", label: "Заблокированные" },
];

const EMPTY_FORM = { email: "", full_name: "", phone: "", password: "" };

function validateForm(values) {
  const errors = {};
  if (!values.email.trim()) errors.email = "Укажите email";
  if (!values.full_name.trim()) errors.full_name = "Укажите ФИО";
  if (values.password.length < 8) errors.password = "Минимум 8 символов";
  return errors;
}

/** Пользователи: поиск, создание библиотекаря, роли и блокировка. */
export default function UsersSection() {
  const { user: currentUser } = useAuth();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [page, setPage] = useState(1);

  const [users, setUsers] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadUsers() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchUsers({
          search,
          role: roleFilter,
          isActive:
            activeFilter === "" ? null : activeFilter === "true",
          page,
          signal: controller.signal,
        });
        if (cancelled) return;
        setUsers(data.results);
        setCount(data.count);
      } catch (requestError) {
        if (cancelled || controller.signal.aborted) return;
        setUsers([]);
        setCount(0);
        setError(
          getErrorMessage(requestError, "Не удалось загрузить пользователей."),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadUsers();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [search, roleFilter, activeFilter, page, reloadKey]);

  function resetFilters() {
    setSearchInput("");
    setSearch("");
    setRoleFilter("");
    setActiveFilter("");
    setPage(1);
  }

  function handleSearch(event) {
    event.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  }

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: "" }));
  }

  async function handleCreate(event) {
    event.preventDefault();
    setActionError("");
    setMessage("");

    const errors = validateForm(form);
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }

    setSaving(true);
    try {
      const created = await createLibrarian({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        password: form.password,
      });
      setMessage(`Библиотекарь «${created.full_name}» создан.`);
      setForm(EMPTY_FORM);
      setFieldErrors({});
      setShowForm(false);
      setPage(1);
      setReloadKey((value) => value + 1);
    } catch (requestError) {
      setFieldErrors(getFieldErrors(requestError));
      setActionError(
        getErrorMessage(requestError, "Не удалось создать библиотекаря."),
      );
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(target, nextRole) {
    if (nextRole === target.role) return;
    const confirmed = window.confirm(
      `Изменить роль «${target.full_name}» на «${getRoleLabel(nextRole)}»?`,
    );
    if (!confirmed) return;

    setActionId(target.id);
    setActionError("");
    setMessage("");
    try {
      await updateUserRole(target.id, nextRole);
      setMessage(`Роль «${target.full_name}» изменена.`);
      setReloadKey((value) => value + 1);
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось изменить роль."),
      );
    } finally {
      setActionId(null);
    }
  }

  async function toggleBlocked(target) {
    const nextActive = !target.is_active;
    const confirmed = window.confirm(
      nextActive
        ? `Разблокировать пользователя «${target.full_name}»?`
        : `Заблокировать пользователя «${target.full_name}»? Он не сможет войти.`,
    );
    if (!confirmed) return;

    setActionId(target.id);
    setActionError("");
    setMessage("");
    try {
      await updateUserStatus(target.id, nextActive);
      setMessage(
        nextActive
          ? `Пользователь «${target.full_name}» разблокирован.`
          : `Пользователь «${target.full_name}» заблокирован.`,
      );
      setReloadKey((value) => value + 1);
    } catch (requestError) {
      setActionError(
        getErrorMessage(requestError, "Не удалось изменить доступ."),
      );
    } finally {
      setActionId(null);
    }
  }

  const isEmpty = !loading && !error && users.length === 0;

  return (
    <section>
      <div className="admin-toolbar">
        <form className="admin-filters" onSubmit={handleSearch}>
          <div className="field">
            <label className="field__label" htmlFor="admin-user-search">
              Поиск
            </label>
            <input
              id="admin-user-search"
              className="input"
              type="search"
              placeholder="ФИО, email или телефон"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="admin-user-role">
              Роль
            </label>
            <select
              id="admin-user-role"
              className="input"
              value={roleFilter}
              onChange={(event) => {
                setRoleFilter(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Все роли</option>
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="admin-user-status">
              Доступ
            </label>
            <select
              id="admin-user-status"
              className="input"
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value);
                setPage(1);
              }}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <button className="button button--primary" type="submit">
            Найти
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={resetFilters}
          >
            Сбросить
          </button>
        </form>

        <button
          type="button"
          className="button button--primary"
          onClick={() => {
            setShowForm((value) => !value);
            setFieldErrors({});
            setActionError("");
          }}
        >
          {showForm ? "Скрыть форму" : "Добавить библиотекаря"}
        </button>
      </div>

      {showForm && (
        <form className="admin-panel admin-form" onSubmit={handleCreate}>
          <h2 className="admin-panel__title">Новый библиотекарь</h2>

          <div className="admin-form__grid">
            <div className="field">
              <label className="field__label" htmlFor="admin-user-email">
                Email
              </label>
              <input
                id="admin-user-email"
                className={`input${fieldErrors.email ? " input--invalid" : ""}`}
                type="email"
                value={form.email}
                onChange={(event) => updateForm("email", event.target.value)}
              />
              {fieldErrors.email && (
                <span className="field__error">{fieldErrors.email}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-user-name">
                ФИО
              </label>
              <input
                id="admin-user-name"
                className={`input${
                  fieldErrors.full_name ? " input--invalid" : ""
                }`}
                value={form.full_name}
                onChange={(event) =>
                  updateForm("full_name", event.target.value)
                }
              />
              {fieldErrors.full_name && (
                <span className="field__error">{fieldErrors.full_name}</span>
              )}
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-user-phone">
                Телефон
              </label>
              <input
                id="admin-user-phone"
                className="input"
                value={form.phone}
                onChange={(event) => updateForm("phone", event.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-user-password">
                Пароль
              </label>
              <input
                id="admin-user-password"
                className={`input${
                  fieldErrors.password ? " input--invalid" : ""
                }`}
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(event) =>
                  updateForm("password", event.target.value)
                }
              />
              {fieldErrors.password && (
                <span className="field__error">{fieldErrors.password}</span>
              )}
            </div>
          </div>

          <div className="admin-form__actions">
            <button
              className="button button--primary"
              type="submit"
              disabled={saving}
            >
              {saving ? "Создаём…" : "Создать"}
            </button>
            <button
              className="button button--ghost"
              type="button"
              onClick={() => setShowForm(false)}
              disabled={saving}
            >
              Отмена
            </button>
          </div>
        </form>
      )}

      {actionError && <ErrorMessage message={actionError} />}
      {message && (
        <p className="dashboard__success" role="status">
          {message}
        </p>
      )}

      {error && (
        <ErrorMessage
          message={error}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      )}

      {loading && <Loader text="Загружаем пользователей…" />}

      {isEmpty && (
        <section className="dashboard__empty">
          <h2 className="dashboard__empty-title">Пользователи не найдены</h2>
          <p className="dashboard__empty-text">
            Измените поиск или фильтры.
          </p>
        </section>
      )}

      {!loading && !error && users.length > 0 && (
        <>
          <p className="dashboard__summary">Всего пользователей: {count}</p>

          <ul className="admin-list">
            {users.map((item) => {
              const isSelf = item.id === currentUser.id;
              const busy = actionId === item.id;
              return (
                <li className="admin-row" key={item.id}>
                  <div className="admin-row__main">
                    <span className="admin-row__title">{item.full_name}</span>
                    <span className="admin-row__meta">{item.email}</span>
                    <span className="admin-row__meta">
                      {item.phone || "телефон не указан"}
                    </span>
                  </div>

                  <div className="admin-row__side">
                    <span
                      className={`status ${
                        item.is_active ? "status--active" : "status--cancelled"
                      }`}
                    >
                      {item.is_active ? "Активен" : "Заблокирован"}
                    </span>

                    <label className="admin-row__role">
                      <span className="admin-row__role-label">Роль</span>
                      <select
                        className="input admin-row__select"
                        value={item.role}
                        disabled={isSelf || busy}
                        onChange={(event) =>
                          changeRole(item, event.target.value)
                        }
                      >
                        {ROLE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <span className="admin-row__meta">
                      с {formatDateTime(item.created_at)}
                    </span>

                    {isSelf ? (
                      <span className="admin-row__hint">это вы</span>
                    ) : (
                      <button
                        type="button"
                        className={`button ${
                          item.is_active
                            ? "button--ghost"
                            : "button--primary"
                        } admin-row__button`}
                        disabled={busy}
                        onClick={() => toggleBlocked(item)}
                      >
                        {busy
                          ? "Сохраняем…"
                          : item.is_active
                            ? "Заблокировать"
                            : "Разблокировать"}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <Pagination page={page} count={count} onChange={setPage} />
        </>
      )}
    </section>
  );
}
