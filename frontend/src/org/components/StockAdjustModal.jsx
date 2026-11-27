/**
 * Adjust a product's stock.
 *
 * Two modes, matching the API:
 *
 *   received / damaged  a relative change — safe while the shop is trading,
 *                       because the server applies it to whatever the row
 *                       holds, under the same lock the order path uses
 *   stocktake           an absolute count — what you have just counted on
 *                       the shelf, which is meant to overwrite
 *
 * The relative mode is the default. Writing an absolute number back is how
 * a shop oversells: an order placed between opening this dialog and saving
 * it would be silently undone.
 */

import { useState } from 'react';

import Modal from './Modal';

export default function StockAdjustModal({ product, onClose, onSave }) {
  const [mode, setMode] = useState('add'); // add | remove | set
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const value = Number(amount);
  const valid = amount !== '' && Number.isFinite(value) && value >= 0 &&
    !(mode !== 'set' && value === 0);

  const resulting =
    mode === 'set'
      ? value
      : mode === 'add'
        ? product.stock + value
        : product.stock - value;

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload =
        mode === 'set'
          ? { stock: value, reason }
          : { delta: mode === 'add' ? value : -value, reason };
      await onSave(payload);
    } catch (err) {
      const first = Object.values(err.fieldErrors || {})[0];
      setError(Array.isArray(first) ? first.join(' ') : err.message);
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`Stock — ${product.name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="button button--ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="button"
            onClick={submit}
            disabled={saving || !valid}
          >
            {saving ? 'Saving…' : 'Apply'}
          </button>
        </>
      }
    >
      {error && <p className="alert alert--error">{error}</p>}

      <p className="muted" style={{ marginTop: 0 }}>
        Currently <strong>{product.stock}</strong> in stock.
      </p>

      <div className="field">
        <label htmlFor="mode">What happened</label>
        <div className="segmented segmented--full" role="group" id="mode">
          <button
            type="button"
            className={mode === 'add' ? 'is-active' : ''}
            onClick={() => setMode('add')}
          >
            Received
          </button>
          <button
            type="button"
            className={mode === 'remove' ? 'is-active' : ''}
            onClick={() => setMode('remove')}
          >
            Removed
          </button>
          <button
            type="button"
            className={mode === 'set' ? 'is-active' : ''}
            onClick={() => setMode('set')}
          >
            Stocktake
          </button>
        </div>
      </div>

      <div className="field">
        <label htmlFor="amount">
          {mode === 'set' ? 'Counted on the shelf' : 'How many units'}
        </label>
        <input
          id="amount"
          type="number"
          min="0"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        {amount !== '' && valid && (
          <p className="muted auth-form__hint">
            {product.stock} → <strong>{Math.max(resulting, 0)}</strong>
            {resulting < 0 && ' — more than you have; the server will refuse this.'}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="reason">Reason (optional)</label>
        <input
          id="reason"
          value={reason}
          placeholder={
            mode === 'add'
              ? 'e.g. delivery received'
              : mode === 'remove'
                ? 'e.g. damaged in transit'
                : 'e.g. monthly stocktake'
          }
          onChange={(event) => setReason(event.target.value)}
        />
      </div>

      {mode === 'set' && (
        <p className="alert alert--error">
          A stocktake overwrites the count. If an order is placed while this
          dialog is open, that sale will be undone. Use “Received” or
          “Removed” unless you have just counted the shelf.
        </p>
      )}
    </Modal>
  );
}
