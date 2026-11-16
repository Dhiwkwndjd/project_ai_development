import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { getErrorMessage, getFieldErrors } from "../api/client";
import { useAuth } from "../auth/context";
import AuthLayout from "../components/AuthLayout";
import ErrorMessage from "../components/ErrorMessage";

const EMPTY_FORM = { email: "", password: "" };

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = location.state?.from?.pathname || "/catalog";

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({ ...prev, [name]: "" }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setGeneralError("");

    if (!form.email.trim() || !form.password) {
      setFieldErrors({
        email: form.email.trim() ? "" : "Введите email",
        password: form.password ? "" : "Введите пароль",
      });
      return;
    }

    setSubmitting(true);
    try {
      await login({ email: form.email.trim(), password: form.password });
      navigate(redirectTo, { replace: true });
    } catch (error) {
      const errors = getFieldErrors(error);
      setFieldErrors(errors);
      if (Object.keys(errors).length) {
        setGeneralError("");
      } else if (error.response?.status === 401) {
        setGeneralError("Неверный email или пароль.");
      } else {
        setGeneralError(getErrorMessage(error, "Не удалось войти. Попробуйте ещё раз."));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Вход"
      subtitle="Войдите, чтобы бронировать книги и следить за очередью."
      footer={
        <span>
          Нет аккаунта?{" "}
          <Link className="link" to="/register">
            Зарегистрироваться
          </Link>
        </span>
      }
    >
      <ErrorMessage message={generalError} />

      <form className="form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label className="field__label" htmlFor="login-email">
            Email
          </label>
          <input
            id="login-email"
            className={`input${fieldErrors.email ? " input--invalid" : ""}`}
            type="email"
            name="email"
            autoComplete="email"
            placeholder="reader1@library.local"
            value={form.email}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.email)}
          />
          {fieldErrors.email && <p className="field__error">{fieldErrors.email}</p>}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="login-password">
            Пароль
          </label>
          <input
            id="login-password"
            className={`input${fieldErrors.password ? " input--invalid" : ""}`}
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={form.password}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.password)}
          />
          {fieldErrors.password && <p className="field__error">{fieldErrors.password}</p>}
        </div>

        {fieldErrors.non_field_errors && (
          <p className="field__error">{fieldErrors.non_field_errors}</p>
        )}

        <button className="button button--primary button--block" type="submit" disabled={submitting}>
          {submitting ? "Вход…" : "Войти"}
        </button>
      </form>
    </AuthLayout>
  );
}
