/**
 * One order, and the actions that move it along.
 *
 * The buttons come from the order's own `next_statuses`, which the server
 * computes from its transition rules. Nothing here knows that confirmed
 * follows pending — so the UI offers exactly what the server will accept,
 * and a rule change on the backend needs no change in this file.
 *
 * Cancelling is kept apart from the other transitions: it returns stock and
 * disappoints a customer, the server demands a reason, and it is the one
 * action here that cannot be undone.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import Modal from '../components/Modal';
import StatusPill from '../components/StatusPill';
import { orgApi } from '../../api/endpoints';
import { formatDate, formatPrice } from '../../utils/format';

/** Turn the server's error body into something to show on the page. */
function readError(error) {
  const fields = error.fieldErrors || {};
  const first = Object.values(fields)[0];
  if (Array.isArray(first)) return first.join(' ');
  return error.message;
}

export default function OrgOrderDetailPage() {
  const { id } = useParams();

  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);

  // Which dialog is open: a status change, or the cancellation.
  const [pending, setPending] = useState(null); // { status, label } | 'cancel'
  const [note, setNote] = useState('');

  const load = useCallback(
    (signal) => {
      setLoading(true);
      setError(null);
      return orgApi.orders
        .get(id, { signal })
        .then((data) => {
          setOrder(data);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === 'AbortError') return;
          setError(
            err.status === 404 ? 'That order does not exist.' : err.message,
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

  const closeDialog = () => {
    setPending(null);
    setNote('');
    setActionError(null);
  };

  const applyStatus = async () => {
    setWorking(true);
    setActionError(null);
    try {
      const updated =
        pending === 'cancel'
          ? await orgApi.orders.cancel(order.id, { reason: note })
          : await orgApi.orders.setStatus(order.id, {
              status: pending.status,
              note,
            });
      // The action returns the whole order, so the page re-renders from the
      // response instead of making a second request for it.
      setOrder(updated);
      setNotice(
        pending === 'cancel'
          ? 'Order cancelled. The stock has been returned to the product.'
          : `Order moved to ${updated.status_display.toLowerCase()}.`,
      );
      closeDialog();
    } catch (err) {
      setActionError(readError(err));
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="org-page">
        <p className="status">Loading order…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="org-page">
        <p className="alert alert--error">{error}</p>
        <Link to="/org/orders">← Back to orders</Link>
      </div>
    );
  }

  // Cancelling has its own button, so it is not offered twice.
  const advanceTo = order.next_statuses.filter((status) => status !== 'cancelled');
  const canCancel = order.next_statuses.includes('cancelled');

  return (
    <div className="org-page">
      <nav className="breadcrumbs">
        <Link to="/org/orders">Orders</Link>
        <span aria-hidden="true">/</span>
        <span className="muted">#{order.id}</span>
      </nav>

      <header className="org-page__header">
        <div>
          <h1>
            Order #{order.id}{' '}
            <StatusPill status={order.status} label={order.status_display} />
          </h1>
          <p className="muted">
            Placed {formatDate(order.created_at)} by{' '}
            <Link to={`/org/customers/${order.customer.id}`}>
              {order.customer.username}
            </Link>
          </p>
        </div>

        <div className="org-actions">
          {advanceTo.map((status) => (
            <button
              key={status}
              type="button"
              className="button"
              onClick={() => setPending({ status, label: status })}
            >
              Mark {status}
            </button>
          ))}
          {canCancel && (
            <button
              type="button"
              className="button button--ghost button--destructive"
              onClick={() => setPending('cancel')}
            >
              Cancel order
            </button>
          )}
          {!order.is_open && (
            <span className="muted">
              This order is finished — no further changes.
            </span>
          )}
        </div>
      </header>

      {notice && <p className="alert alert--success">{notice}</p>}

      <div className="org-columns">
        <div className="org-columns__main">
          <section className="panel">
            <header className="panel__header">
              <h2>What was ordered</h2>
            </header>
            <div className="order-line">
              {order.product.image && (
                <img src={order.product.image} alt="" className="order-line__image" />
              )}
              <div className="order-line__body">
                <p className="order-line__name">{order.product.name}</p>
                <p className="muted">
                  {formatPrice(order.unit_price)} × {order.quantity}
                </p>
              </div>
              <p className="order-line__total">{formatPrice(order.total_price)}</p>
            </div>
            <p className="panel__note muted">
              The unit price is what the product cost when the order was
              placed, so repricing it later does not change this order.
            </p>
          </section>

          <section className="panel">
            <header className="panel__header">
              <h2>History</h2>
            </header>
            <ol className="timeline">
              <li>
                <span className="timeline__dot" />
                <div>
                  <p className="timeline__title">Order placed</p>
                  <p className="muted">
                    {formatDate(order.created_at)} · {order.customer.username}
                  </p>
                </div>
              </li>
              {order.events.map((event) => (
                <li key={event.id}>
                  <span className="timeline__dot" />
                  <div>
                    <p className="timeline__title">
                      {event.from_status_display} → {event.to_status_display}
                    </p>
                    <p className="muted">
                      {formatDate(event.created_at)}
                      {event.changed_by ? ` · ${event.changed_by}` : ' · (account removed)'}
                    </p>
                    {event.note && <p className="timeline__note">“{event.note}”</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <div className="org-columns__side">
          <section className="panel">
            <header className="panel__header">
              <h2>Customer</h2>
            </header>
            <dl className="facts">
              <div>
                <dt>Username</dt>
                <dd>
                  <Link to={`/org/customers/${order.customer.id}`}>
                    {order.customer.username}
                  </Link>
                </dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{order.customer.email || '—'}</dd>
              </div>
              <div>
                <dt>Customer since</dt>
                <dd>{formatDate(order.customer.date_joined)}</dd>
              </div>
            </dl>
          </section>

          {order.status === 'cancelled' && (
            <section className="panel">
              <header className="panel__header">
                <h2>Cancellation</h2>
              </header>
              <dl className="facts">
                <div>
                  <dt>When</dt>
                  <dd>{formatDate(order.cancelled_at)}</dd>
                </div>
                <div>
                  <dt>Stock returned</dt>
                  <dd>{order.stock_restored ? 'Yes' : 'No'}</dd>
                </div>
              </dl>
              {order.cancellation_reason && (
                <p className="panel__note">“{order.cancellation_reason}”</p>
              )}
            </section>
          )}
        </div>
      </div>

      {pending && (
        <Modal
          title={pending === 'cancel' ? 'Cancel this order' : `Mark as ${pending.status}`}
          onClose={closeDialog}
          footer={
            <>
              <button type="button" className="button button--ghost" onClick={closeDialog}>
                Never mind
              </button>
              <button
                type="button"
                className={pending === 'cancel' ? 'button button--danger-solid' : 'button'}
                onClick={applyStatus}
                disabled={working || (pending === 'cancel' && !note.trim())}
              >
                {working
                  ? 'Working…'
                  : pending === 'cancel'
                    ? 'Cancel the order'
                    : `Mark ${pending.status}`}
              </button>
            </>
          }
        >
          {pending === 'cancel' && (
            <p className="alert alert--error">
              The {order.quantity} unit(s) will be returned to{' '}
              {order.product.name}, and the customer will see the order as
              cancelled. This cannot be undone.
            </p>
          )}

          {actionError && <p className="alert alert--error">{actionError}</p>}

          <div className="field">
            <label htmlFor="note">
              {pending === 'cancel' ? 'Reason (required)' : 'Note (optional)'}
            </label>
            <textarea
              id="note"
              rows="3"
              value={note}
              placeholder={
                pending === 'cancel'
                  ? 'e.g. payment failed, customer changed their mind'
                  : 'e.g. payment cleared'
              }
              onChange={(event) => setNote(event.target.value)}
            />
            <p className="muted auth-form__hint">
              Kept in the order's history with your name against it.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
