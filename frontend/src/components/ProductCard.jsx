/** One product in the catalog grid. */

import { Link } from 'react-router-dom';

import { useCart } from '../cart/useCart';
import { formatPrice } from '../utils/format';

export default function ProductCard({ product }) {
  const { addItem } = useCart();
  const soldOut = !product.in_stock;

  return (
    <article className="product-card">
      <Link to={`/products/${product.id}`} className="product-card__image">
        {product.image ? (
          <img src={product.image} alt="" loading="lazy" />
        ) : (
          // Most seeded products have no image; a letter tile keeps the grid
          // even rather than leaving a hole.
          <span className="product-card__placeholder" aria-hidden="true">
            {product.name.charAt(0)}
          </span>
        )}
      </Link>

      <div className="product-card__body">
        <p className="product-card__category">{product.category?.name}</p>
        <h3 className="product-card__name">
          <Link to={`/products/${product.id}`}>{product.name}</Link>
        </h3>
        <p className="product-card__price">{formatPrice(product.price)}</p>
        <p className={`product-card__stock ${soldOut ? 'is-out' : ''}`}>
          {soldOut ? 'Out of stock' : `${product.stock} in stock`}
        </p>

        <button
          type="button"
          className="button"
          disabled={soldOut}
          onClick={() => addItem(product, 1)}
        >
          {soldOut ? 'Unavailable' : 'Add to cart'}
        </button>
      </div>
    </article>
  );
}
