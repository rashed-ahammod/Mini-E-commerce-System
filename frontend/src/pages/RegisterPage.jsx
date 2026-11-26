/**
 * Create an account.
 *
 * Registration returns a token, so a new user is logged in immediately.
 *
 * Django's password rules (length, not too common, not all digits) are
 * enforced on the server. Rather than reimplement them here and risk the two
 * disagreeing, this form shows whatever the API says, per field.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    setSubmitting(true);

    try {
      await register(form);
      navigate('/', { replace: true });
    } catch (err) {
      // ApiError.fieldErrors is DRF's per-field dictionary, e.g.
      // { password: ["This password is too short...", ...] }
      const errors = err.fieldErrors || {};
      setFieldErrors(errors);
      if (!Object.keys(errors).length) setError(err.message);
      setSubmitting(false);
    }
  };

  const errorFor = (field) =>
    fieldErrors[field] && (
      <p className="field__error">
        {Array.isArray(fieldErrors[field])
          ? fieldErrors[field].join(' ')
          : String(fieldErrors[field])}
      </p>
    );

  return (
    <div className="auth-page">
      <form className="card auth-form" onSubmit={handleSubmit} noValidate>
        <h1>Create an account</h1>

        {error && <p className="alert alert--error">{error}</p>}

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            required
            value={form.username}
            onChange={handleChange}
          />
          {errorFor('username')}
        </div>

        <div className="field">
          <label htmlFor="email">Email (optional)</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={form.email}
            onChange={handleChange}
          />
          {errorFor('email')}
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={handleChange}
          />
          {errorFor('password')}
          <p className="muted auth-form__hint">
            At least 8 characters, not entirely numeric, and not a commonly
            used password.
          </p>
        </div>

        <button type="submit" className="button" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>

        <p className="auth-form__footer muted">
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
