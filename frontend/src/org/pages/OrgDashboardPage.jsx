/**
 * The operations dashboard.
 *
 * Everything on this page comes from one request. The backend aggregates it
 * in the database, so widening the window costs nothing extra here.
 *
 * A deliberate choice in how revenue is shown: the API reports both "booked"
 * (every order that was not cancelled) and "realised" (delivered only). The
 * page shows booked as the headline with realised beneath it rather than
 * picking one silently — they answer different questions, and a single
 * figure would mislead whoever was asking the other one.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import StatusPill from '../../components/StatusPill';
import { orgApi } from '../../api/endpoints';
import { formatDate, formatPrice } from '../../utils/format';

const WINDOWS = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
];

export default function OrgDashboardPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(
    (signal) => {
      setLoading(true);
      setError(null);
      return orgApi
        .dashboard({ days }, { signal })
        .then((payload) => {
          setData(payload);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === 'AbortError') return;
          setError(err.message);
          setLoading(false);
        });
    },
    [days],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="org-page">
        <h1>Dashboard</h1>
        <div className="stat-grid">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="stat skeleton" style={{ height: 96 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="org-page">
        <h1>Dashboard</h1>
        <p className="alert alert--error">{error}</p>
      </div>
    );
  }

  const { orders, revenue, customers, catalog, needs_attention: attention } = data;
  const busiest = Math.max(...data.daily.map((day) => day.orders), 1);

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">
            Updated {formatDate(data.generated_at)}
            {loading && ' · refreshing…'}
          </p>
        </div>

        <div className="segmented" role="group" aria-label="Time window">
          {WINDOWS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={days === option.value ? 'is-active' : ''}
              onClick={() => setDays(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      {/* ---- headline figures ---- */}
      <div className="stat-grid">
        <article className="stat">
          <p className="stat__label">Booked revenue</p>
          <p className="stat__value">{formatPrice(revenue.booked)}</p>
          <p className="stat__note">
            {formatPrice(revenue.realised)} delivered ·{' '}
            {formatPrice(revenue.lost_to_cancellations)} cancelled
          </p>
        </article>

        <article className="stat">
          <p className="stat__label">Orders</p>
          <p className="stat__value">{orders.total}</p>
          <p className="stat__note">
            {orders.today} today · {orders.last_7_days} this week
          </p>
        </article>

        <article className={`stat ${orders.open > 0 ? 'stat--action' : ''}`}>
          <p className="stat__label">Open orders</p>
          <p className="stat__value">{orders.open}</p>
          <p className="stat__note">
            {orders.open > 0 ? (
              <Link to="/org/orders?open=true">Work the queue →</Link>
            ) : (
              'Nothing waiting'
            )}
          </p>
        </article>

        <article className="stat">
          <p className="stat__label">Average order</p>
          <p className="stat__value">{formatPrice(revenue.average_order_value)}</p>
          <p className="stat__note">across orders that were not cancelled</p>
        </article>
      </div>

      <div className="org-columns">
        <div className="org-columns__main">
          {/* ---- trend ---- */}
          <section className="panel">
            <header className="panel__header">
              <h2>Orders per day</h2>
              <span className="muted">last {data.window_days} days</span>
            </header>

            <div className="spark" role="img" aria-label={`Orders per day over ${data.window_days} days`}>
              {data.daily.map((day) => (
                <div key={day.date} className="spark__col" title={`${day.date}: ${day.orders} order(s), ${formatPrice(day.revenue)}`}>
                  <div
                    className={`spark__bar ${day.orders === 0 ? 'is-empty' : ''}`}
                    // Quiet days are drawn as a visible sliver rather than
                    // nothing, so a run of zeros reads as "no orders" and
                    // not as missing data.
                    style={{ height: `${Math.max((day.orders / busiest) * 100, 3)}%` }}
                  />
                </div>
              ))}
            </div>
          </section>

          {/* ---- status breakdown ---- */}
          <section className="panel">
            <header className="panel__header">
              <h2>Orders by status</h2>
            </header>
            <ul className="breakdown">
              {data.orders_by_status.map((row) => (
                <li key={row.status}>
                  <StatusPill status={row.status} label={row.label} />
                  <span className="breakdown__count">{row.count}</span>
                  <span className="breakdown__value muted">{formatPrice(row.value)}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* ---- best sellers ---- */}
          <section className="panel">
            <header className="panel__header">
              <h2>Best sellers</h2>
              <span className="muted">excludes cancelled orders</span>
            </header>
            {data.top_products.length === 0 ? (
              <p className="status">Nothing sold in this window yet.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Units</th>
                    <th>Orders</th>
                    <th>Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_products.map((product) => (
                    <tr key={product.product_id}>
                      <td>{product.name}</td>
                      <td>{product.units_sold}</td>
                      <td>{product.order_count}</td>
                      <td>{formatPrice(product.revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        {/* ---- the side column is what to do next ---- */}
        <div className="org-columns__side">
          <section className="panel">
            <header className="panel__header">
              <h2>Awaiting action</h2>
            </header>
            {attention.orders_awaiting_action.length === 0 ? (
              <p className="status">No pending orders.</p>
            ) : (
              <ul className="stack">
                {attention.orders_awaiting_action.map((order) => (
                  <li key={order.id}>
                    <Link to={`/org/orders/${order.id}`} className="stack__row">
                      <span>
                        <strong>#{order.id}</strong> {order.customer}
                        <span className="muted"> · {order.product}</span>
                      </span>
                      <span>{formatPrice(order.total_price)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <header className="panel__header">
              <h2>Running low</h2>
              <span className="muted">≤ {data.low_stock_threshold}</span>
            </header>
            {attention.low_stock_products.length === 0 ? (
              <p className="status">Everything is well stocked.</p>
            ) : (
              <ul className="stack">
                {attention.low_stock_products.map((product) => (
                  <li key={product.id}>
                    <Link to={`/org/products?low_stock=${data.low_stock_threshold}`} className="stack__row">
                      <span>{product.name}</span>
                      <span className={product.stock === 0 ? 'tag tag--muted' : 'tag tag--warn'}>
                        {product.stock === 0 ? 'Out' : product.stock}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <header className="panel__header">
              <h2>At a glance</h2>
            </header>
            <dl className="facts">
              <div>
                <dt>Customers</dt>
                <dd>{customers.total}</dd>
              </div>
              <div>
                <dt>Have ordered</dt>
                <dd>{customers.with_orders}</dd>
              </div>
              <div>
                <dt>New this week</dt>
                <dd>{customers.new_last_7_days}</dd>
              </div>
              <div>
                <dt>Products</dt>
                <dd>{catalog.products}</dd>
              </div>
              <div>
                <dt>Out of stock</dt>
                <dd>{catalog.out_of_stock}</dd>
              </div>
              <div>
                <dt>Units held</dt>
                <dd>{catalog.units_in_stock}</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}
