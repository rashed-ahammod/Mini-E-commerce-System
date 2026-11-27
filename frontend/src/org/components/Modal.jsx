/**
 * A small modal dialog.
 *
 * Used where an action needs a note or a reason before it is carried out —
 * cancelling an order, revoking an account. Those are the actions someone
 * may have to explain later, so the server requires the text and the UI
 * collects it rather than firing the request straight from a button.
 *
 * Escape closes it, the backdrop closes it, and focus moves into the dialog
 * when it opens so the keyboard works without reaching for the mouse.
 */

import { useEffect, useRef } from 'react';

export default function Modal({ title, children, onClose, footer }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);

    // Move focus in, so the first field is ready to type into.
    const focusable = dialogRef.current?.querySelector(
      'input, textarea, select, button',
    );
    focusable?.focus();

    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div
      className="modal__backdrop"
      // A click on the backdrop closes; a click inside must not, hence the
      // stopPropagation on the dialog itself.
      onClick={onClose}
      role="presentation"
    >
      <div
        className="modal"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal__header">
          <h2>{title}</h2>
          <button
            type="button"
            className="modal__close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <div className="modal__body">{children}</div>

        {footer && <footer className="modal__footer">{footer}</footer>}
      </div>
    </div>
  );
}
