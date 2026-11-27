/**
 * The account's own profile.
 *
 * Email, phone and address are required, because an order has to reach a
 * real person at a real address — and because checkout offers this address
 * as the place to deliver to. The page says plainly what is still missing
 * rather than waiting for the customer to discover it at checkout.
 *
 * Validation rules (what counts as a phone number, how much address is
 * enough) live on the server. Rather than keep a second copy here that could
 * disagree, the form shows whatever the API says, per field. The one check it
 * does make is "has anything changed?", so Save cannot send an empty PATCH.
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { authApi } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';
import { formatDate } from '../utils/format';

/** The fields this form owns, in the order they appear. */
const EDITABLE = ['first_name', 'last_name', 'email', 'phone', 'address'];

const LABELS = {
  email: 'Email address',
  phone: 'Phone number',
  address: 'Delivery address',
};

export default function ProfilePage() {
  const { refreshUser } = useAuth();
  const location = useLocation();
  // Set by checkout when it sends someone here to fill in what is missing.
  const returnTo = location.state?.returnTo;

  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    authApi.profile
      .get({ signal: controller.signal })
      .then((data) => {
        setProfile(data);
        setForm(Object.fromEntries(EDITABLE.map((key) => [key, data[key] ?? ''])));
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setLoadError(err.message);
        setLoading(false);
      });

    return () => controller.abort();
  }, []);

  // Only what actually changed is sent, so a save never rewrites a field the
  // customer did not touch.
  const changes = useMemo(() => {
    if (!profile || !form) return {};
    return Object.fromEntries(
      EDITABLE.filter((key) => form[key].trim() !== (profile[key] ?? '')).map(
        (key) => [key, form[key].trim()],
      ),
    );
  }, [profile, form]);

  const isDirty = Object.keys(changes).length > 0;

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    setSaved(false);
    // Clear this field's error as soon as it is edited: the message was
    // about the old value.
    setFieldErrors((current) => {
      if (!current[name]) return current;
      const { [name]: _removed, ...rest } = current;
      return rest;
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!isDirty) return;

    setSaving(true);
    setError(null);
    setFieldErrors({});

    try {
      const updated = await authApi.profile.update(changes);
      setProfile(updated);
      setForm(Object.fromEntries(EDITABLE.map((key) => [key, updated[key] ?? ''])));
      setSaved(true);
      // The navbar and checkout read these details off the auth context.
      await refreshUser().catch(() => {});
    } catch (err) {
      const errors = err.fieldErrors || {};
      setFieldErrors(errors);
      if (!Object.keys(errors).length) setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const errorFor = (field) =>
    fieldErrors[field] && (
      <p className="field__error" id={`${field}-error`}>
        {Array.isArray(fieldErrors[field])
          ? fieldErrors[field].join(' ')
          : String(fieldErrors[field])}
      </p>
    );

  if (loading) return <p className="status">Loading your profile…</p>;

  if (loadError) {
    return (
      <div className="profile">
        <p className="alert alert--error">{loadError}</p>
      </div>
    );
  }

  const missing = profile.missing_details ?? [];
  const initial = (profile.first_name || profile.username).charAt(0).toUpperCase();
  const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ');

  return (
    <div className="profile">
      <header className="profile__header card">
        <span className="profile__avatar" aria-hidden="true">
          {initial}
        </span>
        <div className="profile__identity">
          <h1>{fullName || profile.username}</h1>
          <p className="muted">
            @{profile.username}
            {profile.role && profile.role !== 'customer' && (
              <>
                {' · '}
                <span className="pill pill--accent">{profile.role}</span>
              </>
            )}
          </p>
          <p className="muted profile__since">
            Member since {formatDate(profile.date_joined)}
          </p>
        </div>
        <span
          className={`pill ${profile.profile_complete ? 'pill--ok' : 'pill--warn'}`}
        >
          {profile.profile_complete ? 'Ready to order' : 'Details needed'}
        </span>
      </header>

      {missing.length > 0 && (
        <div className="alert alert--warn">
          <strong>Your profile needs a little more.</strong> Add your{' '}
          {missing.map((field) => LABELS[field]?.toLowerCase() ?? field).join(', ')} so
          your orders can be delivered and we can tell you how they are going.
        </div>
      )}

      {saved && !isDirty && (
        <p className="alert alert--success">
          Profile saved.
          {returnTo && (
            <>
              {' '}
              <Link to={returnTo}>Back to checkout →</Link>
            </>
          )}
        </p>
      )}

      {error && <p className="alert alert--error">{error}</p>}

      <div className="profile__grid">
        <form className="card profile__form" onSubmit={handleSubmit} noValidate>
          <h2>Contact &amp; delivery details</h2>
          <p className="muted profile__form-intro">
            Checkout offers this address as the place to deliver to, so keeping
            it current saves typing it out every time.
          </p>

          <div className="field-row">
            <div className="field">
              <label htmlFor="first_name">First name</label>
              <input
                id="first_name"
                name="first_name"
                autoComplete="given-name"
                value={form.first_name}
                onChange={handleChange}
              />
              {errorFor('first_name')}
            </div>

            <div className="field">
              <label htmlFor="last_name">Last name</label>
              <input
                id="last_name"
                name="last_name"
                autoComplete="family-name"
                value={form.last_name}
                onChange={handleChange}
              />
              {errorFor('last_name')}
            </div>
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
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? 'email-error' : undefined}
              value={form.email}
              onChange={handleChange}
            />
            {errorFor('email')}
            <p className="field__hint">Where order confirmations are sent.</p>
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
              aria-invalid={Boolean(fieldErrors.phone)}
              aria-describedby={fieldErrors.phone ? 'phone-error' : undefined}
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
              rows="4"
              autoComplete="street-address"
              required
              placeholder={'House 12, Road 5\nDhanmondi, Dhaka 1205'}
              aria-invalid={Boolean(fieldErrors.address)}
              aria-describedby={fieldErrors.address ? 'address-error' : undefined}
              value={form.address}
              onChange={handleChange}
            />
            {errorFor('address')}
            <p className="field__hint">
              Street, area and city — enough for a courier to find you.
            </p>
          </div>

          <div className="profile__actions">
            <button type="submit" className="button" disabled={saving || !isDirty}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            {isDirty && !saving && (
              <span className="muted">You have unsaved changes.</span>
            )}
          </div>
        </form>

        <aside className="card profile__aside">
          <h2>Account</h2>
          <dl className="facts">
            <div>
              <dt>Username</dt>
              <dd>{profile.username}</dd>
            </div>
            <div>
              <dt>Account type</dt>
              <dd>{profile.role === 'customer' ? 'Customer' : profile.role}</dd>
            </div>
            {profile.department && (
              <div>
                <dt>Department</dt>
                <dd>{profile.department}</dd>
              </div>
            )}
            <div>
              <dt>Joined</dt>
              <dd>{formatDate(profile.date_joined)}</dd>
            </div>
          </dl>

          <p className="muted profile__aside-note">
            Your username cannot be changed — past orders are recorded against
            it. <Link to="/orders">See your orders →</Link>
          </p>
        </aside>
      </div>
    </div>
  );
}
