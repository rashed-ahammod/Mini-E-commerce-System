/**
 * Placeholder card shown while the catalog loads.
 *
 * Matching the real card's shape keeps the grid from jumping when the data
 * arrives, which is more comfortable than a single centred spinner.
 */

export default function ProductCardSkeleton() {
  return (
    <article className="product-card product-card--skeleton" aria-hidden="true">
      <div className="product-card__media skeleton" />
      <div className="product-card__body">
        <div className="skeleton skeleton--line skeleton--short" />
        <div className="skeleton skeleton--line" />
        <div className="skeleton skeleton--line skeleton--medium" />
        <div className="product-card__footer">
          <div className="skeleton skeleton--line skeleton--short" />
        </div>
      </div>
    </article>
  );
}
