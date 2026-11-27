/**
 * Move an order along, from wherever it is listed.
 *
 * The order queue is where staff actually work: a page of orders to be
 * confirmed, packed and shipped. Having to open each one, act, and come back
 * turns a morning's work into a few hundred round trips, so the same actions
 * live on the row itself.
 *
 * The buttons come from the order's own `next_statuses`, which the server
 * computes from its transition rules. Nothing here knows that confirmed
 * follows pending — so the UI offers exactly what the server will accept,
 * and a rule change on the backend needs no change in this file.
 *
 * Cancelling is kept apart from the rest: it returns stock and disappoints a
 * customer, the server demands a reason, and it is the one action here that
 * cannot be undone. It always asks first. Advancing does not, because
 * "confirm this order" is the ordinary case and a dialog on every one of
 * them is the thing that makes people stop using the queue.
 */

import { useState } from 'react';

import Modal from './Modal';
import { orgApi } from '../../api/endpoints';

/** The verb for each move, so a button reads as an action, not a state. */
const VERB = {
  confirmed: 'Confirm',
  processing: 'Start packing',
  shipped: 'Mark shipped',
  delivered: 'Mark delivered',
};

/** Pull the most useful sentence out of a DRF error body. */
function readError(error) {
  const fields = error.fieldErrors || {};
  const first = Object.values(fields)[0];
  if (Array.isArray(first)) return first.join(' ');
  return error.message;
}

export default function StatusActions({ order, onChanged, compact = false }) {
  const [working, setWorking] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState(null);

  const next = order.next_statuses || [];
  const advanceTo = next.filter((status) => status !== 'cancelled');
  const canCancel = next.includes('cancelled');

  if (!next.length) {
    return compact ? (
      <span className="muted status-actions__done">Finished</span>
    ) : null;
  }

  const advance = async (status) => {
    setWorking(status);
    setError(null);
    try {
      // The action returns the whole order, so the caller can re-render from
      // the response instead of making a second request for it.
      const updated = await orgApi.orders.setStatus(order.id, { status });
      onChanged(updated);
    } catch (err) {
      setError(readError(err));
    } finally {
      setWorking(null);
    }
  };

  const cancel = async () => {
    setWorking('cancelled');
    setError(null);
    try {
      const updated = await orgApi.orders.cancel(order.id, { reason });
      onChanged(updated);
      setCancelling(false);
      setReason('');
    } catch (err) {
      setError(readError(err));
    } finally {
      setWorking(null);
    }
  };

  return (
    <div className="status-actions">
      {error && <p className="field__error status-actions__error">{error}</p>}

      <div className="status-actions__buttons">
        {advanceTo.map((status) => (
          <button
            key={status}
            type="button"
            className="button button--small"
            disabled={Boolean(working)}
            onClick={() => advance(status)}
          >
            {working === status ? 'Working…' : VERB[status] || `Mark ${status}`}
          </button>
        ))}

        {canCancel && (
          <button
            type="button"
            className="button button--ghost button--small button--destructive"
            disabled={Boolean(working)}
            onClick={() => {
              setCancelling(true);
              setError(null);
            }}
          >
            Cancel
          </button>
        )}
      </div>

      {cancelling && (
        <Modal
          title={`Cancel order #${order.id}`}
          onClose={() => {
            setCancelling(false);
            setReason('');
            setError(null);
          }}
          footer={
            <>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => {
                  setCancelling(false);
                  setReason('');
                }}
              >
                Never mind
              </button>
              <button
                type="button"
                className="button button--danger-solid"
                onClick={cancel}
                disabled={Boolean(working) || !reason.trim()}
              >
                {working ? 'Working…' : 'Cancel the order'}
              </button>
            </>
          }
        >
          <p className="alert alert--error">
            The {order.quantity} unit(s) will be returned to{' '}
            {order.product.name}, and the customer will see the order as
            cancelled. This cannot be undone.
          </p>

          {error && <p className="alert alert--error">{error}</p>}

          <div className="field">
            <label htmlFor={`cancel-reason-${order.id}`}>Reason (required)</label>
            <textarea
              id={`cancel-reason-${order.id}`}
              rows="3"
              value={reason}
              placeholder="e.g. payment failed, customer changed their mind"
              onChange={(event) => setReason(event.target.value)}
            />
            <p className="field__hint">
              Kept in the order&rsquo;s history with your name against it.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
