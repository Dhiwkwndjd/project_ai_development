import axios from "axios";

const ACCESS_KEY = "library.access";
const REFRESH_KEY = "library.refresh";

const BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

/** Хранение токенов в одном месте. */
export const tokenStorage = {
  getAccess() {
    return localStorage.getItem(ACCESS_KEY);
  },
  getRefresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  save({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  saveAccess(access) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

let authFailureHandler = null;

/** AuthContext подписывается, чтобы разлогинить пользователя при сбое refresh. */
export function setAuthFailureHandler(handler) {
  authFailureHandler = handler;
}

api.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess();
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

let refreshPromise = null;

function requestNewAccessToken() {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) {
    return Promise.reject(new Error("Нет refresh-токена"));
  }
  // Отдельный axios: без интерцепторов, чтобы не зациклиться.
  return axios
    .post(`${BASE_URL}/auth/refresh/`, { refresh })
    .then(({ data }) => {
      tokenStorage.saveAccess(data.access);
      return data.access;
    });
}

const NO_REFRESH_URLS = ["/auth/login/", "/auth/register/", "/auth/refresh/"];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;

    if (
      !response ||
      response.status !== 401 ||
      !config ||
      config._retry ||
      NO_REFRESH_URLS.some((url) => config.url.includes(url))
    ) {
      return Promise.reject(error);
    }

    config._retry = true;

    try {
      // Один запрос refresh на все параллельные 401.
      refreshPromise = refreshPromise || requestNewAccessToken();
      const access = await refreshPromise;
      refreshPromise = null;

      config.headers.Authorization = `Bearer ${access}`;
      return api(config);
    } catch (refreshError) {
      refreshPromise = null;
      tokenStorage.clear();
      if (authFailureHandler) authFailureHandler();
      return Promise.reject(refreshError);
    }
  },
);

function collectFieldErrors(data) {
  if (!data || typeof data !== "object") return {};
  // ApiErrorMixin кладёт ошибки полей во вложенный объект `fields`.
  const source =
    data.fields && typeof data.fields === "object" && !Array.isArray(data.fields)
      ? data.fields
      : data;
  const fields = {};
  Object.entries(source).forEach(([key, value]) => {
    if (key === "detail" || key === "code") return;
    fields[key] = Array.isArray(value) ? value.join(" ") : String(value);
  });
  return fields;
}

/** Понятное сообщение из ответа DRF. */
export function getErrorMessage(error, fallback = "Что-то пошло не так. Попробуйте ещё раз.") {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  const fieldErrors = collectFieldErrors(data);
  const first = Object.values(fieldErrors)[0];
  return first || fallback;
}

/** Ошибки по полям формы. */
export function getFieldErrors(error) {
  return collectFieldErrors(error?.response?.data);
}
