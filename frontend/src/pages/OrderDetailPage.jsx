/** One order. Another user's order id returns 404 from the API. */

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { orderApi } from '../api/endpoints';
import { formatDate, formatPrice } from '../utils/format';

export default function OrderDetailPage() {
  const { id } = useParams();

  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    orderApi
      .get(id)
      .then((data) => {
        setOrder(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(
          err.status === 404
            ? 'That order does not exist, or it is not yours.'
            : err.message,
        );
        setLoading(false);
      });
  }, [id]);

  if (loading) return <p className="status">Loading order…</p>;

  if (error) {
    return (
      <div>
        <p className="alert alert--error">{error}</p>
        <Link to="/orders">← Back to my orders</Link>
      </div>
    );
  }

  return (
    <div className="order-detail">
      <Link to="/orders" className="product-detail__back">
        ← Back to my orders
      </Link>

      <h1>Order #{order.id}</h1>
      <p className="muted">Placed {formatDate(order.created_at)}</p>

      <div className="card order-detail__card">
        <dl className="order-detail__list">
          <div>
            <dt>Product</dt>
            <dd>
              <Link to={`/products/${order.product.id}`}>{order.product.name}</Link>
            </dd>
          </div>
          <div>
            <dt>Quantity</dt>
            <dd>{order.quantity}</dd>
          </div>
          <div>
            <dt>Price paid per unit</dt>
            <dd>{formatPrice(order.unit_price)}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd className="order-detail__total">{formatPrice(order.total_price)}</dd>
          </div>
          <div>
            <dt>Ordered by</dt>
            <dd>{order.user}</dd>
          </div>
        </dl>

        <p className="muted order-detail__note">
          The unit price is the price at the time the order was placed, so it
          does not change if the product is repriced later.
        </p>
      </div>

      <div className="card order-detail__card">
        <h2 className="order-detail__subhead">Delivery</h2>
        <dl className="order-detail__list">
          <div>
            <dt>Address</dt>
            {/* Whitespace is preserved, so a typed-out address keeps the
                lines the customer put it on. */}
            <dd className="order-detail__address">
              {order.delivery_address || '—'}
            </dd>
          </div>
          <div>
            <dt>Contact number</dt>
            <dd>{order.delivery_phone || '—'}</dd>
          </div>
        </dl>

        <p className="muted order-detail__note">
          This is where the order was sent when it was placed. Changing your{' '}
          <Link to="/profile">profile address</Link> affects future orders, not
          this one.
        </p>
      </div>
    </div>
  );
}
