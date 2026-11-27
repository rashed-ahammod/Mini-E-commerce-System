/**
 * An order status as a coloured pill.
 *
 * Shared by the shop and the operations console: a customer watching an
 * order and the staff member moving it along are looking at the same fact,
 * and it should look the same to both.
 *
 * The colour carries meaning, so it is defined once here rather than at each
 * call site: cancelled must never look like delivered on one screen and like
 * pending on another.
 */

const TONE = {
  pending: 'wait',
  confirmed: 'info',
  processing: 'info',
  shipped: 'go',
  delivered: 'ok',
  cancelled: 'off',
};

export default function StatusPill({ status, label }) {
  return (
    <span className={`pill pill--${TONE[status] || 'info'}`}>
      {label || status}
    </span>
  );
}
