import { Link } from "react-router-dom";

import { getRoleLabel } from "../auth/roles";
import { useAuth } from "../auth/context";
import SiteHeader from "../components/SiteHeader";
import "../styles/home.css";

export default function HomePage() {
  const { user } = useAuth();

  return (
    <div className="home">
      <SiteHeader />

      <main className="home__content">
        <section className="home__card">
          <p className="home__eyebrow">Личный кабинет</p>
          <h1 className="home__title">Здравствуйте, {user.full_name}!</h1>
          <p className="home__lead">
            Вы вошли в систему. Откройте{" "}
            <Link className="link" to="/catalog">
              каталог книг
            </Link>
            , чтобы найти издание и посмотреть свободные экземпляры.
          </p>

          {user.role === "reader" ? (
            <p className="home__lead">
              Ваши брони — в разделе{" "}
              <Link className="link" to="/my">
                «Мои брони»
              </Link>
              , ожидание книг — в разделе{" "}
              <Link className="link" to="/my/queue">
                «Моя очередь»
              </Link>
              .
            </p>
          ) : (
            <p className="home__lead">
              Выдача книг, возвраты и очередь читателей — в разделе{" "}
              <Link className="link" to="/librarian">
                «Выдача»
              </Link>
              .
              {user.role === "admin" && (
                <>
                  {" "}
                  Пользователи, фонд и все брони — в{" "}
                  <Link className="link" to="/admin">
                    «Админке»
                  </Link>
                  .
                </>
              )}
            </p>
          )}

          <dl className="home__details">
            <div className="home__detail">
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div className="home__detail">
              <dt>Роль</dt>
              <dd>{getRoleLabel(user.role)}</dd>
            </div>
            <div className="home__detail">
              <dt>Телефон</dt>
              <dd>{user.phone || "не указан"}</dd>
            </div>
          </dl>

          <p className="home__note">
            Сессия сохраняется между перезагрузками страницы, а access-токен обновляется
            автоматически.
          </p>
        </section>
      </main>
    </div>
  );
}
