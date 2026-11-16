import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { getRoleLabel } from "../auth/roles";
import { useAuth } from "../auth/context";
import ErrorMessage from "./ErrorMessage";
import "../styles/header.css";

function getInitials(fullName = "") {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return parts
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function navClass({ isActive }) {
  return `site-header__link${isActive ? " site-header__link--active" : ""}`;
}

/** Шапка авторизованных страниц: навигация и аккаунт. */
export default function SiteHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState("");

  async function handleLogout() {
    setError("");
    setLoggingOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setError("Не удалось выйти. Попробуйте ещё раз.");
      setLoggingOut(false);
    }
  }

  if (!user) return null;

  const isReader = user.role === "reader";

  return (
    <div className="site-header">
      <header className="site-header__bar">
        <Link className="site-header__brand" to="/catalog">
          <span className="site-header__brand-mark" aria-hidden="true">
            Б
          </span>
          <span className="site-header__brand-name">Библиотека</span>
        </Link>

        <nav className="site-header__nav" aria-label="Разделы">
          <NavLink className={navClass} to="/catalog">
            Каталог
          </NavLink>
          {isReader ? (
            <>
              <NavLink className={navClass} to="/my">
                Мои брони
              </NavLink>
              <NavLink className={navClass} to="/my/queue">
                Очередь
              </NavLink>
            </>
          ) : (
            <NavLink className={navClass} to="/librarian">
              Выдача
            </NavLink>
          )}
          {user.role === "admin" && (
            <NavLink className={navClass} to="/admin">
              Админка
            </NavLink>
          )}
          <NavLink className={navClass} to="/" end>
            Кабинет
          </NavLink>
        </nav>

        <div className="site-header__account">
          <span className="site-header__avatar" aria-hidden="true">
            {getInitials(user.full_name)}
          </span>
          <span className="site-header__account-text">
            <span className="site-header__account-name">{user.full_name}</span>
            <span className="site-header__account-role">{getRoleLabel(user.role)}</span>
          </span>
          <button
            type="button"
            className="button button--ghost site-header__logout"
            onClick={handleLogout}
            disabled={loggingOut}
          >
            {loggingOut ? "Выходим…" : "Выйти"}
          </button>
        </div>
      </header>

      {error && (
        <div className="site-header__alert">
          <ErrorMessage message={error} />
        </div>
      )}
    </div>
  );
}
