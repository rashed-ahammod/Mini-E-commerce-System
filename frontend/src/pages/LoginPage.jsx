/**
 * Log in.
 *
 * After a successful login the user is sent back where they were heading —
 * ProtectedRoute puts that location in `state.from` when it redirects here.
 *
 * The page also publishes two sample logins, because this project is meant
 * to be looked at. One is a customer; the other is organization staff, which
 * opens the operations console at /org — the half of the system a shopper
 * never sees. Without that second login there is no way for a reviewer to
 * reach it, and a feature nobody can find may as well not be built.
 *
 * The published account is deliberately `staff`, not `admin`: it reaches the
 * dashboard, the order queue and the catalog, but not the management of
 * other people's accounts. Both are created by
 * `manage.py seed_data --demo-user`, which resets their passwords, so what
 * is printed here is always what works.
 */

import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import ColdStartNotice from '../components/ColdStartNotice';
import { useAuth } from '../auth/useAuth';

/** The sample accounts, exactly as seed_data creates them. */
const SAMPLE_LOGINS = [
  {
    id: 'staff',
    label: 'Organization staff',
    username: 'salesman',
    password: '@111111@',
    blurb: 'Opens the operations console: dashboard, orders, catalog, customers.',
  },
  {
    id: 'customer',
    label: 'Customer',
    username: 'demo',
    password: 'demo12345',
    blurb: 'Shops, places orders and sees their own order history.',
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from?.pathname || '/';

  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  // Filling the form rather than logging straight in: the reviewer sees
  // which account they are about to use, and the password is no longer
  // something to retype by hand from a box above.
  const fillFromSample = (sample) => {
    setForm({ username: sample.username, password: sample.password });
    setError(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const loggedIn = await login(form);
      // Send organization users to the console unless they were heading
      // somewhere specific, which is the case when a guard redirected them
      // here. Customers always land where they were going.
      const destination =
        location.state?.from || !loggedIn.is_organization ? redirectTo : '/org';
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-form" onSubmit={handleSubmit}>
        <h1>Log in</h1>

        {error && <p className="alert alert--error">{error}</p>}

        {/* Only while a login is actually hanging, and only when the API is
            the one on Render's free tier. See <ColdStartNotice>. */}
        <ColdStartNotice waiting={submitting} />

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
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={handleChange}
          />
        </div>

        <button type="submit" className="button" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>

        <p className="auth-form__footer muted">
          No account yet? <Link to="/register">Create one</Link>
        </p>
      </form>

      <aside className="sample-logins card">
        <h2>Sample accounts</h2>
        <p className="muted sample-logins__intro">
          This is a portfolio project, so both sides of it are open to look
          at. Pick one to fill the form.
        </p>

        <ul className="sample-logins__list">
          {SAMPLE_LOGINS.map((sample) => (
            <li key={sample.id} className="sample-login">
              <div className="sample-login__head">
                <span className="pill pill--accent">{sample.label}</span>
                <button
                  type="button"
                  className="button button--ghost button--small"
                  onClick={() => fillFromSample(sample)}
                >
                  Use this
                </button>
              </div>

              <dl className="sample-login__creds">
                <div>
                  <dt>Username</dt>
                  <dd>
                    <code>{sample.username}</code>
                  </dd>
                </div>
                <div>
                  <dt>Password</dt>
                  <dd>
                    <code>{sample.password}</code>
                  </dd>
                </div>
              </dl>

              <p className="sample-login__blurb muted">{sample.blurb}</p>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
