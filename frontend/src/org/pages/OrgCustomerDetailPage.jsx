/**
 * One customer: what they have spent, what they have ordered, and whether
 * they can still sign in.
 *
 * Deactivating is the strongest thing on this page, so it is deliberately
 * undramatic to reverse and explicit about what it does and does not touch:
 * their orders stay exactly where they are, and the account can be let back
 * in with one click. What it does do is end the session immediately, which
 * the dialog says plainly.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import Modal from '../components/Modal';
import StatusPill from '../components/StatusPill';
import { orgApi } from '../../api/endpoints';
import { formatDate, formatPrice } from '../../utils/format';

export default function OrgCustomerDetailPage() {
  const { id } = useParams();

  const [customer, setCustomer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [actionError, setActionError] = useState(null);
  const [working, setWorking] = useState(false);

  const load = useCallback(
    (signal) => {
      setLoading(true);
      setError(null);
      return orgApi.customers
        .get(id, { signal })
        .then((data) => {
          setCustomer(data);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === 'AbortError') return;
          setError(
            err.status === 404
              ? 'No such customer. Organization accounts are managed under Accounts.'
              : err.message,
          );
          setLoading(false);
        });
    },
    [id],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const deactivate = async () => {
    setWorking(true);
    setActionError(null);
    try {
      const updated = await orgApi.customers.deactivate(customer.id, { reason });
      setCustomer(updated);
      setNotice(
        `${updated.username} can no longer sign in. Their orders are unchanged.`,
      );
      setConfirming(false);
      setReason('');
    } catch (err) {
      const first = Object.values(err.fieldErrors || {})[0];
      setActionError(Array.isArray(first) ? first.join(' ') : err.message);
    } finally {
      setWorking(false);
    }
  };

  const activate = async () => {
    setWorking(true);
    setActionError(null);
    try {
      const updated = await orgApi.customers.activate(customer.id);
      setCustomer(updated);
      setNotice(`${updated.username} can sign in again.`);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="org-page">
        <p className="status">Loading customer…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="org-page">
        <p className="alert alert--error">{error}</p>
        <Link to="/org/customers">← Back to customers</Link>
      </div>
    );
  }

  return (
    <div className="org-page">
      <nav className="breadcrumbs">
        <Link to="/org/customers">Customers</Link>
        <span aria-hidden="true">/</span>
        <span className="muted">{customer.username}</span>
      </nav>

      <header className="org-page__header">
        <div>
          <h1>
            {customer.username}{' '}
            <span className={customer.is_active ? 'pill pill--ok' : 'pill pill--off'}>
              {customer.is_active ? 'Active' : 'Deactivated'}
            </span>
          </h1>
          <p className="muted">
            {customer.email || 'No email on file'} · customer since{' '}
            {formatDate(customer.date_joined)}
          </p>
        </div>

        <div className="org-actions">
          {customer.is_active ? (
            <button
              type="button"
              className="button button--ghost button--destructive"
              onClick={() => setConfirming(true)}
            >
              Deactivate account
            </button>
          ) : (
            <button
              type="button"
              className="button"
              onClick={activate}
              disabled={working}
            >
              {working ? 'Working…' : 'Reactivate account'}
            </button>
          )}
        </div>
      </header>

      {notice && <p className="alert alert--success">{notice}</p>}
      {actionError && <p className="alert alert--error">{actionError}</p>}

      <div className="stat-grid">
        <article className="stat">
          <p className="stat__label">Spent</p>
          <p className="stat__value">{formatPrice(customer.total_spent)}</p>
          <p className="stat__note">excludes cancelled orders</p>
        </article>
        <article className="stat">
          <p className="stat__label">Orders</p>
          <p className="stat__value">{customer.order_count}</p>
          <p className="stat__note">including any that were cancelled</p>
        </article>
        <article className="stat">
          <p className="stat__label">Last order</p>
          <p className="stat__value stat__value--small">
            {customer.last_order_at ? formatDate(customer.last_order_at) : 'Never'}
          </p>
        </article>
        <article className="stat">
          <p className="stat__label">Last signed in</p>
          <p className="stat__value stat__value--small">
            {customer.last_login ? formatDate(customer.last_login) : 'Never'}
          </p>
        </article>
      </div>

      <section className="panel">
        <header className="panel__header">
          <h2>Contact details</h2>
          {!customer.profile_complete && (
            <span className="pill pill--warn">Incomplete</span>
          )}
        </header>
        <dl className="facts">
          <div>
            <dt>Email</dt>
            <dd>{customer.email || '—'}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{customer.phone || '—'}</dd>
          </div>
          <div>
            <dt>Default delivery address</dt>
            <dd className="facts__address">{customer.address || '—'}</dd>
          </div>
        </dl>
        <p className="panel__note muted">
          {customer.profile_complete
            ? 'Their default address. Each order carries the address it was placed to, which may differ.'
            : 'This customer cannot check out until they fill in the missing details. Only they can change them.'}
        </p>
      </section>

      <section className="panel">
        <header className="panel__header">
          <h2>Recent orders</h2>
          <Link to={`/org/orders?customer_username=${customer.username}`}>
            See all →
          </Link>
        </header>

        {customer.recent_orders.length === 0 ? (
          <p className="status" style={{ padding: 24 }}>
            This customer has not ordered anything yet.
          </p>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Order</th>
                <th>Product</th>
                <th>Qty</th>
                <th>Total</th>
                <th>Status</th>
                <th>Placed</th>
              </tr>
            </thead>
            <tbody>
              {customer.recent_orders.map((order) => (
                <tr key={order.id}>
                  <td>
                    <Link to={`/org/orders/${order.id}`} className="table__link">
                      #{order.id}
                    </Link>
                  </td>
                  <td>{order.product.name}</td>
                  <td>{order.quantity}</td>
                  <td className="nums">{formatPrice(order.total_price)}</td>
                  <td>
                    <StatusPill status={order.status} label={order.status_display} />
                  </td>
                  <td className="muted">{formatDate(order.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {confirming && (
        <Modal
          title={`Deactivate ${customer.username}?`}
          onClose={() => setConfirming(false)}
          footer={
            <>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button--danger-solid"
                onClick={deactivate}
                disabled={working || !reason.trim()}
              >
                {working ? 'Working…' : 'Deactivate'}
              </button>
            </>
          }
        >
          <p>
            They will be signed out immediately and will not be able to sign
            in again. Their {customer.order_count} order
            {customer.order_count === 1 ? '' : 's'} and{' '}
            {formatPrice(customer.total_spent)} of history stay exactly as
            they are, and you can let them back in at any time.
          </p>

          {actionError && <p className="alert alert--error">{actionError}</p>}

          <div className="field">
            <label htmlFor="reason">Reason (required)</label>
            <input
              id="reason"
              value={reason}
              placeholder="e.g. fraudulent orders, customer request"
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
        </Modal>
      )}
    </div>
  );
}
