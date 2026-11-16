import { Link } from "react-router-dom";

import "../styles/auth.css";

/** Общий каркас экранов входа и регистрации. */
export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="auth">
      <aside className="auth__aside">
        <Link to="/" className="auth__brand">
          <span className="auth__brand-mark" aria-hidden="true">
            Б
          </span>
          <span className="auth__brand-name">Библиотека</span>
        </Link>
        <p className="auth__aside-text">
          Бронируйте книги, вставайте в очередь на занятые экземпляры и следите за сроками
          возврата в одном месте.
        </p>
        <ul className="auth__features">
          <li>Каталог книг и свободные экземпляры</li>
          <li>Честная очередь и удержание на 48 часов</li>
          <li>История ваших броней</li>
        </ul>
      </aside>

      <main className="auth__main">
        <div className="auth__card">
          <header className="auth__header">
            <h1 className="auth__title">{title}</h1>
            {subtitle && <p className="auth__subtitle">{subtitle}</p>}
          </header>

          {children}

          {footer && <div className="auth__footer">{footer}</div>}
        </div>
        <p className="auth__note">Учебный проект · бронирование книг</p>
      </main>
    </div>
  );
}
