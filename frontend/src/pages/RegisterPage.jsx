/**
 * Create an account.
 *
 * Registration returns a token, so a new user is logged in immediately.
 *
 * Email, phone and address are asked for here rather than later: the shop
 * cannot deliver an order or tell anyone about it without them, and
 * collecting them once at sign-up means checkout is prefilled from the very
 * first purchase instead of stopping a new customer mid-way to ask.
 *
 * Django's password rules (length, not too common, not all digits), and what
 * counts as a usable phone number or address, are all enforced on the
 * server. Rather than reimplement them here and risk the two disagreeing,
 * this form shows whatever the API says, per field.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: '',
    email: '',
    phone: '',
    address: '',
    password: '',
  });
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
          <label htmlFor="email">
            Email address <span className="field__required">required</span>
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={handleChange}
          />
          {errorFor('email')}
          <p className="field__hint">Where your order confirmations go.</p>
        </div>

        <div className="field">
          <label htmlFor="phone">
            Phone number <span className="field__required">required</span>
          </label>
          <input
            id="phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            required
            placeholder="+880 1711 123456"
            value={form.phone}
            onChange={handleChange}
          />
          {errorFor('phone')}
          <p className="field__hint">So the courier can reach you on the day.</p>
        </div>

        <div className="field">
          <label htmlFor="address">
            Delivery address <span className="field__required">required</span>
          </label>
          <textarea
            id="address"
            name="address"
            rows="3"
            autoComplete="street-address"
            required
            placeholder={'House 12, Road 5\nDhanmondi, Dhaka 1205'}
            value={form.address}
            onChange={handleChange}
          />
          {errorFor('address')}
          <p className="field__hint">
            Saved to your profile — checkout offers it as the place to deliver
            to, and you can change it any time.
          </p>
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
