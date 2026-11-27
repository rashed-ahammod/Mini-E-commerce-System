/**
 * Where an order has got to, as a line of steps.
 *
 * The organization moves an order through pending → confirmed → processing
 * → shipped → delivered. Until now a customer could not see any of that:
 * the shop recorded a status it never showed, so the whole lifecycle the
 * console manages was invisible to the person actually waiting for the
 * parcel. "Where is my order?" is the most common question a shop gets, and
 * this is the answer to it.
 *
 * Cancelled is not a step on the line — it is the line stopping — so it gets
 * its own treatment rather than a sixth box that implies progress.
 *
 * The staff note attached to a cancellation is deliberately NOT shown. The
 * console describes it as kept in the order's history with the author's name
 * against it, which is an internal audit record: staff write candidly in it,
 * and a field written for colleagues should not be republished to the
 * customer. The API does not send it here, and this should not start asking
 * for it — the date is enough to say what happened and when.
 */

import { formatDate } from '../utils/format';

const STEPS = [
  { status: 'pending', label: 'Placed', note: 'We have your order.' },
  { status: 'confirmed', label: 'Confirmed', note: 'Payment and stock checked.' },
  { status: 'processing', label: 'Packing', note: 'Being picked and packed.' },
  { status: 'shipped', label: 'Shipped', note: 'On its way to you.' },
  { status: 'delivered', label: 'Delivered', note: 'Handed over. Enjoy it.' },
];

export default function OrderProgress({ status, statusDisplay, cancelledAt }) {
  if (status === 'cancelled') {
    return (
      <div className="progress progress--stopped">
        <p className="progress__stopped-title">This order was cancelled</p>
        {cancelledAt && (
          <p className="muted">Cancelled on {formatDate(cancelledAt)}.</p>
        )}
        <p className="muted progress__stopped-note">
          Anything it was holding has been returned to stock, and you have not
          been charged for it. Get in touch if this was not expected.
        </p>
      </div>
    );
  }

  const current = STEPS.findIndex((step) => step.status === status);
  // An unrecognised status should not silently render an empty line.
  const reached = current === -1 ? 0 : current;

  return (
    <ol className="progress" aria-label={`Order status: ${statusDisplay || status}`}>
      {STEPS.map((step, index) => {
        const state =
          index < reached ? 'done' : index === reached ? 'current' : 'todo';

        return (
          <li key={step.status} className={`progress__step progress__step--${state}`}>
            <span className="progress__marker" aria-hidden="true">
              {state === 'done' ? '✓' : index + 1}
            </span>
            <span className="progress__body">
              <span className="progress__label">{step.label}</span>
              <span className="progress__note">{step.note}</span>
            </span>
            {state === 'current' && (
              <span className="visually-hidden">— current step</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
