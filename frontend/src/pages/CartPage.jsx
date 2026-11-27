/**
 * The cart and checkout.
 *
 * The backend models one order as one product and one quantity, so checkout
 * posts one request per cart line. That means a checkout can partly succeed:
 * if the third line is out of stock, the first two orders are already placed.
 * Rather than hide that, the page removes the lines that succeeded, keeps the
 * ones that failed with the server's message next to them, and says plainly
 * what happened.
 *
 * Delivery details are collected once and sent with every line, so one
 * basket goes to one address. The address can be typed, or taken from the
 * profile — see <DeliveryFields>. Either way the server decides whether it
 * is good enough to deliver to, and an error about the address is shown
 * against the address rather than repeated beside every product.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import DeliveryFields from '../components/DeliveryFields';
import { orderApi } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';
import { useCart } from '../cart/useCart';
import { formatPrice } from '../utils/format';

/** Errors that belong to the delivery form rather than to a cart line. */
const DELIVERY_FIELDS = ['delivery_address', 'delivery_phone', 'use_profile_address'];

export default function CartPage() {
  const { items, total, updateQuantity, removeItem, clear } = useCart();
  const { isAuthenticated, user, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [submitting, setSubmitting] = useState(false);
  const [lineErrors, setLineErrors] = useState({});
  const [deliveryErrors, setDeliveryErrors] = useState({});
  const [summary, setSummary] = useState(null);

  const profileAddress = user?.address ?? '';
  const profilePhone = user?.phone ?? '';

  // Start on the saved address when there is one: it is the right answer
  // almost every time, and it is still shown in the field to be checked.
  const [delivery, setDelivery] = useState({
    address: '',
    phone: '',
    useProfile: false,
    saveToProfile: false,
  });

  // The profile arrives a moment after the page on a fresh load, so the
  // default is applied once it is known — and only while the customer has
  // not already typed something of their own.
  useEffect(() => {
    if (!profileAddress) return;
    setDelivery((current) =>
      current.address.trim() || current.useProfile
        ? current
        : { ...current, useProfile: true, address: profileAddress },
    );
  }, [profileAddress]);

  const updateDelivery = (changes) => {
    setDelivery((current) => ({ ...current, ...changes }));
    setDeliveryErrors({});
  };

  const handleCheckout = async () => {
    setSubmitting(true);
    setLineErrors({});
    setDeliveryErrors({});
    setSummary(null);

    const placed = [];
    const failed = {};
    let deliveryProblem = null;

    // Sequential on purpose: each order changes the stock the next one is
    // checked against, so firing them in parallel would make the outcome
    // depend on timing.
    for (const item of items) {
      try {
        const order = await orderApi.create({
          productId: item.id,
          quantity: item.quantity,
          deliveryAddress: delivery.address,
          deliveryPhone: delivery.phone,
          useProfileAddress: delivery.useProfile,
          saveToProfile: delivery.saveToProfile,
        });
        placed.push(order);
      } catch (error) {
        const fields = error.fieldErrors || {};
        const aboutDelivery = DELIVERY_FIELDS.filter((field) => fields[field]);

        if (aboutDelivery.length) {
          // The address is wrong for the whole basket, not for this one
          // product. Stop rather than collect the same complaint once per
          // line — and stop before placing any more orders to an address
          // the server has already refused.
          deliveryProblem = Object.fromEntries(
            aboutDelivery.map((field) => [field, fields[field]]),
          );
          break;
        }

        failed[item.id] = error.message;
      }
    }

    // Keep only the lines that did not go through.
    placed.forEach((order) => removeItem(order.product.id));

    // An order that saved its address to the profile has changed the account
    // behind the scenes. Re-read it, or the navbar and a later visit to this
    // page would keep offering the address this checkout just replaced.
    if (placed.length && delivery.saveToProfile) {
      await refreshUser().catch(() => {
        // Not worth failing a placed order over: the next page load fixes it.
      });
    }

    setLineErrors(failed);
    if (deliveryProblem) setDeliveryErrors(deliveryProblem);
    setSubmitting(false);

    const problems = Object.keys(failed).length + (deliveryProblem ? 1 : 0);

    if (placed.length && !problems) {
      navigate('/orders', { state: { justOrdered: placed.length } });
      return;
    }

    setSummary({ placed: placed.length, failed: Object.keys(failed).length });
  };

  if (items.length === 0) {
    return (
      <div className="cart">
        <h1>Your cart</h1>
        {summary?.placed > 0 && (
          <p className="alert alert--success">
            {summary.placed} order{summary.placed === 1 ? '' : 's'} placed.{' '}
            <Link to="/orders">View your orders →</Link>
          </p>
        )}
        <p className="status">
          Your cart is empty. <Link to="/">Browse products →</Link>
        </p>
      </div>
    );
  }

  const hasDeliveryProblem = Object.keys(deliveryErrors).length > 0;

  return (
    <div className="cart">
      <h1>Your cart</h1>

      {summary && (
        <p className={summary.failed || hasDeliveryProblem ? 'alert alert--error' : 'alert alert--success'}>
          {summary.placed > 0
            ? `${summary.placed} order(s) placed. `
            : 'No orders were placed. '}
          {hasDeliveryProblem
            ? 'Check the delivery details below.'
            : summary.failed > 0 &&
              `${summary.failed} item(s) could not be ordered — see the messages below.`}
        </p>
      )}

      <div className="cart__layout">
        <div className="cart__main">
          <ul className="cart__list">
            {items.map((item) => (
              <li key={item.id} className="cart__item card">
                <Link to={`/products/${item.id}`} className="cart__item-media">
                  {item.image ? (
                    <img src={item.image} alt="" loading="lazy" />
                  ) : (
                    <span className="product-card__placeholder" aria-hidden="true">
                      {item.name.charAt(0)}
                    </span>
                  )}
                </Link>

                <div className="cart__item-main">
                  <Link to={`/products/${item.id}`} className="cart__item-name">
                    {item.name}
                  </Link>
                  <p className="muted">{formatPrice(item.price)} each</p>
                  {lineErrors[item.id] && (
                    <p className="field__error">{lineErrors[item.id]}</p>
                  )}
                </div>

                <div className="cart__item-quantity field">
                  <label htmlFor={`quantity-${item.id}`}>Qty</label>
                  <input
                    id={`quantity-${item.id}`}
                    type="number"
                    min="1"
                    max={item.stock}
                    value={item.quantity}
                    onChange={(event) =>
                      updateQuantity(item.id, Number(event.target.value))
                    }
                  />
                </div>

                <p className="cart__item-total">
                  {formatPrice(Number(item.price) * item.quantity)}
                </p>

                <button
                  type="button"
                  className="button button--danger button--small"
                  onClick={() => removeItem(item.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>

          {/* Only worth asking a logged-in customer: an anonymous visitor
              has no profile to offer, and has to log in to order anyway. */}
          {isAuthenticated && (
            <div className="card">
              <DeliveryFields
                address={delivery.address}
                phone={delivery.phone}
                useProfile={delivery.useProfile}
                saveToProfile={delivery.saveToProfile}
                profileAddress={profileAddress}
                profilePhone={profilePhone}
                onChange={updateDelivery}
                errors={deliveryErrors}
                disabled={submitting}
              />
            </div>
          )}
        </div>

        <aside className="cart__summary card">
          <h2>Summary</h2>

          <dl className="cart__totals">
            <div>
              <dt>
                {items.length} item{items.length === 1 ? '' : 's'}
              </dt>
              <dd>{formatPrice(total)}</dd>
            </div>
            <div>
              <dt>Delivery</dt>
              <dd className="muted">Calculated at dispatch</dd>
            </div>
          </dl>

          <div className="cart__grand-total">
            <span>Estimated total</span>
            <strong className="cart__total">{formatPrice(total)}</strong>
          </div>

          <p className="muted cart__note">
            The server calculates the final price of every order.
          </p>

          <div className="cart__actions">
            {isAuthenticated ? (
              <button
                type="button"
                className="button button--block"
                onClick={handleCheckout}
                disabled={submitting}
              >
                {submitting ? 'Placing orders…' : 'Place order'}
              </button>
            ) : (
              <Link
                to="/login"
                state={{ from: { pathname: '/cart' } }}
                className="button button--block"
              >
                Log in to check out
              </Link>
            )}

            <button
              type="button"
              className="button button--ghost button--block"
              onClick={clear}
              disabled={submitting}
            >
              Empty cart
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
