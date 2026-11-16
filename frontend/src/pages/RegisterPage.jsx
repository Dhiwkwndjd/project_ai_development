import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getErrorMessage, getFieldErrors } from "../api/client";
import { useAuth } from "../auth/context";
import AuthLayout from "../components/AuthLayout";
import ErrorMessage from "../components/ErrorMessage";

const EMPTY_FORM = { full_name: "", email: "", phone: "", password: "", password2: "" };

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => ({ ...prev, [name]: "" }));
  }

  function validate() {
    const errors = {};
    if (!form.full_name.trim()) errors.full_name = "Укажите ФИО";
    if (!form.email.trim()) {
      errors.email = "Введите email";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      errors.email = "Похоже, email указан с ошибкой";
    }
    if (!form.password) {
      errors.password = "Придумайте пароль";
    } else if (form.password.length < 8) {
      errors.password = "Пароль должен быть не короче 8 символов";
    }
    if (form.password2 !== form.password) {
      errors.password2 = "Пароли не совпадают";
    }
    return errors;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setGeneralError("");

    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    const payload = {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      password: form.password,
    };

    setSubmitting(true);
    try {
      // После регистрации AuthContext сразу выполняет вход.
      await register(payload);
      navigate("/catalog", { replace: true });
    } catch (error) {
      const serverErrors = getFieldErrors(error);
      setFieldErrors(serverErrors);
      if (Object.keys(serverErrors).length) {
        setGeneralError("");
      } else {
        setGeneralError(getErrorMessage(error, "Не удалось зарегистрироваться."));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Регистрация"
      subtitle="Новый аккаунт создаётся с ролью читателя."
      footer={
        <span>
          Уже есть аккаунт?{" "}
          <Link className="link" to="/login">
            Войти
          </Link>
        </span>
      }
    >
      <ErrorMessage message={generalError} />

      <form className="form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label className="field__label" htmlFor="register-name">
            ФИО
          </label>
          <input
            id="register-name"
            className={`input${fieldErrors.full_name ? " input--invalid" : ""}`}
            type="text"
            name="full_name"
            autoComplete="name"
            placeholder="Иван Петров"
            value={form.full_name}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.full_name)}
          />
          {fieldErrors.full_name && <p className="field__error">{fieldErrors.full_name}</p>}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="register-email">
            Email
          </label>
          <input
            id="register-email"
            className={`input${fieldErrors.email ? " input--invalid" : ""}`}
            type="email"
            name="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={form.email}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.email)}
          />
          {fieldErrors.email && <p className="field__error">{fieldErrors.email}</p>}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="register-phone">
            Телефон <span className="field__hint">— необязательно</span>
          </label>
          <input
            id="register-phone"
            className={`input${fieldErrors.phone ? " input--invalid" : ""}`}
            type="tel"
            name="phone"
            autoComplete="tel"
            placeholder="+7 900 000-00-00"
            value={form.phone}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.phone)}
          />
          {fieldErrors.phone && <p className="field__error">{fieldErrors.phone}</p>}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="register-password">
            Пароль
          </label>
          <input
            id="register-password"
            className={`input${fieldErrors.password ? " input--invalid" : ""}`}
            type="password"
            name="password"
            autoComplete="new-password"
            placeholder="Не короче 8 символов"
            value={form.password}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.password)}
          />
          {fieldErrors.password && <p className="field__error">{fieldErrors.password}</p>}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="register-password2">
            Пароль ещё раз
          </label>
          <input
            id="register-password2"
            className={`input${fieldErrors.password2 ? " input--invalid" : ""}`}
            type="password"
            name="password2"
            autoComplete="new-password"
            placeholder="Повторите пароль"
            value={form.password2}
            onChange={handleChange}
            disabled={submitting}
            aria-invalid={Boolean(fieldErrors.password2)}
          />
          {fieldErrors.password2 && <p className="field__error">{fieldErrors.password2}</p>}
        </div>

        <button className="button button--primary button--block" type="submit" disabled={submitting}>
          {submitting ? "Создаём аккаунт…" : "Зарегистрироваться"}
        </button>
      </form>
    </AuthLayout>
  );
}
