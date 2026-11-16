import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/admin", label: "Панель", end: true },
  { to: "/admin/reports", label: "Отчёты" },
  { to: "/admin/logs", label: "Журнал" },
];

function linkClass({ isActive }) {
  return `admin-nav__link${isActive ? " admin-nav__link--active" : ""}`;
}

/** Навигация между разделами админ-панели. */
export default function AdminNav() {
  return (
    <nav className="admin-nav" aria-label="Разделы администрирования">
      {LINKS.map((link) => (
        <NavLink key={link.to} className={linkClass} to={link.to} end={link.end}>
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
