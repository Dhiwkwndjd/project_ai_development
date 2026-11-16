import { useState } from "react";

import AdminNav from "../components/admin/AdminNav";
import BooksSection from "../components/admin/BooksSection";
import LoansSection from "../components/admin/LoansSection";
import QueueSection from "../components/admin/QueueSection";
import UsersSection from "../components/admin/UsersSection";
import SiteHeader from "../components/SiteHeader";
import "../styles/dashboard.css";
import "../styles/admin.css";

const TABS = [
  { id: "users", label: "Пользователи" },
  { id: "books", label: "Книги и экземпляры" },
  { id: "loans", label: "Бронирования" },
  { id: "queue", label: "Очередь" },
];

/** Административная панель: доступ проверяется на backend и в RoleRoute. */
export default function AdminPage() {
  const [tab, setTab] = useState("users");

  return (
    <div className="page">
      <SiteHeader />

      <main className="dashboard admin">
        <div className="dashboard__head">
          <p className="dashboard__eyebrow">Администрирование</p>
          <h1 className="dashboard__title">Панель управления</h1>
          <p className="dashboard__lead">
            Пользователи и роли, фонд библиотеки, все бронирования и очередь
            читателей. Каждое действие проверяется на сервере.
          </p>
        </div>

        <AdminNav />

        <div
          className="dashboard__tabs"
          role="tablist"
          aria-label="Разделы админ-панели"
        >
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={`dashboard__tab${
                tab === item.id ? " dashboard__tab--active" : ""
              }`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === "users" && <UsersSection />}
        {tab === "books" && <BooksSection />}
        {tab === "loans" && <LoansSection />}
        {tab === "queue" && <QueueSection />}
      </main>
    </div>
  );
}
