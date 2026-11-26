/**
 * The cart and checkout.
 *
 * The backend models one order as one product and one quantity, so checkout
 * posts one request per cart line. That means a checkout can partly succeed:
 * if the third line is out of stock, the first two orders are already placed.
 * Rather than hide that, the page removes the lines that succeeded, keeps the
 * ones that failed with the server's message next to them, and says plainly
 * what happened.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { orderApi } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';
import { useCart } from '../cart/useCart';
import { formatPrice } from '../utils/format';

export default function CartPage() {
  const { items, total, updateQuantity, removeItem, clear } = useCart();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [submitting, setSubmitting] = useState(false);
  const [lineErrors, setLineErrors] = useState({});
  const [summary, setSummary] = useState(null);

  const handleCheckout = async () => {
    setSubmitting(true);
    setLineErrors({});
    setSummary(null);

    const placed = [];
    const failed = {};

    // Sequential on purpose: each order changes the stock the next one is
    // checked against, so firing them in parallel would make the outcome
    // depend on timing.
    for (const item of items) {
      try {
        const order = await orderApi.create({
          productId: item.id,
          quantity: item.quantity,
        });
        placed.push(order);
      } catch (error) {
        failed[item.id] = error.message;
      }
    }

    // Keep only the lines that did not go through.
    placed.forEach((order) => removeItem(order.product.id));

    setLineErrors(failed);
    setSubmitting(false);

    if (placed.length && !Object.keys(failed).length) {
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

  return (
    <div className="cart">
      <h1>Your cart</h1>

      {summary && (
        <p className={summary.failed ? 'alert alert--error' : 'alert alert--success'}>
          {summary.placed > 0
            ? `${summary.placed} order(s) placed. `
            : 'No orders were placed. '}
          {summary.failed > 0 &&
            `${summary.failed} item(s) could not be ordered — see the messages below.`}
        </p>
      )}

      <ul className="cart__list">
        {items.map((item) => (
          <li key={item.id} className="cart__item card">
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

      <div className="cart__footer card">
        <div>
          <p className="muted">Estimated total</p>
          <p className="cart__total">{formatPrice(total)}</p>
          <p className="muted cart__note">
            The server calculates the final price of every order.
          </p>
        </div>

        <div className="cart__actions">
          <button type="button" className="button button--ghost" onClick={clear}>
            Empty cart
          </button>

          {isAuthenticated ? (
            <button
              type="button"
              className="button"
              onClick={handleCheckout}
              disabled={submitting}
            >
              {submitting ? 'Placing orders…' : 'Place order'}
            </button>
          ) : (
            <Link to="/login" state={{ from: { pathname: '/cart' } }} className="button">
              Log in to check out
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
