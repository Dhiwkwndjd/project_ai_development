import { createContext, useContext } from "react";

export const AuthContext = createContext(null);

/** Доступ к состоянию авторизации из любого компонента. */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth должен использоваться внутри AuthProvider");
  }
  return context;
}
