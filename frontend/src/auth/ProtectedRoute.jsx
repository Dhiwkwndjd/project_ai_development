import { Navigate, Outlet, useLocation } from "react-router-dom";

import Loader from "../components/Loader";
import { useAuth } from "./context";

/** Пускает только авторизованных; запоминает адрес, куда пользователь шёл. */
export function ProtectedRoute() {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return <Loader full height="page" text="Проверяем авторизацию…" />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}

/** Пускает только пользователей с нужной ролью, остальных возвращает в каталог. */
export function RoleRoute({ roles }) {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return <Loader full height="page" text="Проверяем авторизацию…" />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!roles.includes(user.role)) {
    return <Navigate to="/catalog" replace />;
  }

  return <Outlet />;
}

/** Страницы входа и регистрации: авторизованному здесь делать нечего. */
export function PublicOnlyRoute() {
  const { user, initializing } = useAuth();

  if (initializing) {
    return <Loader full height="page" text="Проверяем авторизацию…" />;
  }

  if (user) {
    return <Navigate to="/catalog" replace />;
  }

  return <Outlet />;
}
