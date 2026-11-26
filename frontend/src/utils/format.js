/**
 * Display helpers.
 *
 * Prices arrive from DRF as strings ("999.00") rather than numbers, which is
 * what keeps decimals exact. They are only converted for display, never for
 * arithmetic that is sent back to the server — the backend calculates every
 * total itself.
 */

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatPrice(value) {
  const number = Number(value);
  return Number.isFinite(number) ? currencyFormatter.format(number) : '—';
}

export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date);
}
