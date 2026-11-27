/**
 * Where an order should go, asked once at checkout.
 *
 * The address field comes first, because typing an address is the thing that
 * always works. Underneath it sits the shortcut: one toggle that fills the
 * field from the profile and keeps it in step, so the saved address is
 * offered rather than assumed.
 *
 * Checking the toggle does two things, and both matter. It fills the field,
 * so what is on screen is what will be delivered to — a blank or stale box
 * above a ticked "use my profile address" is how people end up surprised.
 * And it sends `use_profile_address`, so the server reads the address off the
 * profile itself rather than trusting a value that travelled through the
 * browser.
 *
 * When there is no saved address, the toggle says so and points at the
 * profile instead of being quietly unavailable.
 */

import { Link } from 'react-router-dom';

export default function DeliveryFields({
  address,
  phone,
  useProfile,
  saveToProfile,
  profileAddress,
  profilePhone,
  onChange,
  errors = {},
  disabled = false,
}) {
  const hasProfileAddress = Boolean(profileAddress?.trim());

  const toggleProfile = (checked) => {
    onChange({
      useProfile: checked,
      // Fill the field from the profile so the form shows what will happen.
      // Unticking leaves the text in place to edit rather than wiping it —
      // it is almost always the right starting point for a one-off address.
      address: checked ? profileAddress : address,
      phone: checked && !phone.trim() ? profilePhone ?? '' : phone,
      // The two options contradict each other: there is nothing to save
      // back to the profile when the address came from it.
      saveToProfile: checked ? false : saveToProfile,
    });
  };

  const errorFor = (field) =>
    errors[field] && (
      <p className="field__error" id={`${field}-error`}>
        {Array.isArray(errors[field]) ? errors[field].join(' ') : String(errors[field])}
      </p>
    );

  return (
    <section className="delivery">
      <header className="delivery__header">
        <h2>Delivery details</h2>
        <p className="muted">Where should this order go?</p>
      </header>

      <div className="field">
        <label htmlFor="delivery_address">
          Delivery address <span className="field__required">required</span>
        </label>
        <textarea
          id="delivery_address"
          name="delivery_address"
          rows="4"
          autoComplete="street-address"
          required
          // Read-only rather than disabled while the profile address is in
          // use: a disabled field is dropped from the form and greys out to
          // the point of being hard to read, and the address is the one
          // thing on this page a customer will want to double-check.
          readOnly={useProfile}
          aria-readonly={useProfile}
          aria-invalid={Boolean(errors.delivery_address)}
          aria-describedby={
            errors.delivery_address ? 'delivery_address-error' : undefined
          }
          placeholder={'House 12, Road 5\nDhanmondi, Dhaka 1205'}
          value={address}
          onChange={(event) => onChange({ address: event.target.value })}
          disabled={disabled}
        />
        {errorFor('delivery_address')}
        <p className="field__hint">
          Street, area and city — enough for a courier to find you.
        </p>
      </div>

      {/* The shortcut, directly below the field it fills. */}
      <div className="delivery__options">
        <label
          className={`option ${useProfile ? 'option--on' : ''} ${
            hasProfileAddress ? '' : 'option--unavailable'
          }`}
        >
          <input
            type="checkbox"
            checked={useProfile}
            disabled={disabled || !hasProfileAddress}
            onChange={(event) => toggleProfile(event.target.checked)}
          />
          <span className="option__body">
            <span className="option__title">Use my profile address</span>
            {hasProfileAddress ? (
              <span className="option__detail">{profileAddress}</span>
            ) : (
              <span className="option__detail">
                You have not saved one yet.{' '}
                <Link to="/profile" state={{ returnTo: '/cart' }}>
                  Add an address to your profile →
                </Link>
              </span>
            )}
          </span>
        </label>
        {errorFor('use_profile_address')}

        {!useProfile && (
          <label className={`option ${saveToProfile ? 'option--on' : ''}`}>
            <input
              type="checkbox"
              checked={saveToProfile}
              disabled={disabled}
              onChange={(event) => onChange({ saveToProfile: event.target.checked })}
            />
            <span className="option__body">
              <span className="option__title">
                Save this as my profile address
              </span>
              <span className="option__detail">
                {hasProfileAddress
                  ? 'Replaces the address saved on your profile, for next time.'
                  : 'Saves it to your profile so next time it is one click.'}
              </span>
            </span>
          </label>
        )}
      </div>

      <div className="field">
        <label htmlFor="delivery_phone">Contact number for this delivery</label>
        <input
          id="delivery_phone"
          name="delivery_phone"
          type="tel"
          autoComplete="tel"
          placeholder={profilePhone || '+880 1711 123456'}
          aria-invalid={Boolean(errors.delivery_phone)}
          aria-describedby={errors.delivery_phone ? 'delivery_phone-error' : undefined}
          value={phone}
          onChange={(event) => onChange({ phone: event.target.value })}
          disabled={disabled}
        />
        {errorFor('delivery_phone')}
        <p className="field__hint">
          {profilePhone
            ? `Leave blank to use ${profilePhone}, the number on your profile.`
            : 'The courier calls this number if they cannot find you.'}
        </p>
      </div>
    </section>
  );
}
