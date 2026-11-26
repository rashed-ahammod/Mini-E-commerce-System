/**
 * Page controls driven by DRF's pagination response.
 *
 * DRF returns { count, next, previous, results }. `next`/`previous` are full
 * URLs, but this app keeps the page number in its own state, so all that is
 * needed from them is whether they exist.
 */

export default function Pagination({ page, count, pageSize, onChange }) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  if (count === 0 || totalPages === 1) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, count);

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="button button--ghost button--small"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
      >
        ← Previous
      </button>

      <span className="pagination__status">
        {first}–{last} of {count} · page {page} of {totalPages}
      </span>

      <button
        type="button"
        className="button button--ghost button--small"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
      >
        Next →
      </button>
    </nav>
  );
}
