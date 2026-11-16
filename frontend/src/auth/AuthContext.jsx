import { useCallback, useEffect, useMemo, useState } from "react";

import { api, setAuthFailureHandler, tokenStorage } from "../api/client";
import { AuthContext } from "./context";

/**
 * Состояние авторизации: пользователь, вход, регистрация, выход.
 * Запросы к API собраны здесь, страницы только вызывают методы.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  const clearSession = useCallback(() => {
    tokenStorage.clear();
    setUser(null);
  }, []);

  // Сбой обновления токена в api/client.js означает конец сессии.
  useEffect(() => {
    setAuthFailureHandler(clearSession);
    return () => setAuthFailureHandler(null);
  }, [clearSession]);

  // При старте восстанавливаем пользователя по сохранённому access-токену.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      if (!tokenStorage.getAccess()) {
        setInitializing(false);
        return;
      }
      try {
        const { data } = await api.get("/auth/me/");
        if (!cancelled) setUser(data);
      } catch {
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const login = useCallback(async ({ email, password }) => {
    const { data } = await api.post("/auth/login/", { email, password });
    tokenStorage.save({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(
    async (payload) => {
      await api.post("/auth/register/", payload);
      // Backend при регистрации не выдаёт токены — входим сразу после создания.
      return login({ email: payload.email, password: payload.password });
    },
    [login],
  );

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh();
    try {
      if (refresh) {
        await api.post("/auth/logout/", { refresh });
      }
    } catch {
      // Даже если backend недоступен, локальную сессию закрываем.
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, initializing, login, register, logout }),
    [user, initializing, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
