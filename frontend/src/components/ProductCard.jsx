/** One product in the catalog grid. */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useCart } from '../cart/useCart';
import { formatPrice } from '../utils/format';

export default function ProductCard({ product }) {
  const { addItem } = useCart();
  const [added, setAdded] = useState(false);
  // A product can carry a broken link, so the placeholder has to be reachable
  // from a failed load, not only from a missing URL.
  const [imageFailed, setImageFailed] = useState(false);

  const soldOut = !product.in_stock;
  const lowStock = product.in_stock && product.stock <= 5;
  const showImage = product.image && !imageFailed;

  const handleAdd = () => {
    addItem(product, 1);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1600);
  };

  return (
    <article className={`product-card ${soldOut ? 'is-sold-out' : ''}`}>
      <Link
        to={`/products/${product.id}`}
        className="product-card__media"
        aria-label={product.name}
      >
        {showImage ? (
          <img
            src={product.image}
            alt={product.name}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="product-card__placeholder" aria-hidden="true">
            {product.name.charAt(0)}
          </span>
        )}

        {soldOut && <span className="tag tag--muted">Sold out</span>}
        {lowStock && <span className="tag tag--warn">Only {product.stock} left</span>}
      </Link>

      <div className="product-card__body">
        <p className="product-card__category">{product.category?.name}</p>

        <h3 className="product-card__name">
          <Link to={`/products/${product.id}`}>{product.name}</Link>
        </h3>

        <p className="product-card__description">{product.description}</p>

        <div className="product-card__footer">
          <p className="product-card__price">{formatPrice(product.price)}</p>
          <button
            type="button"
            className={`button button--small ${added ? 'button--success' : ''}`}
            disabled={soldOut}
            onClick={handleAdd}
          >
            {soldOut ? 'Unavailable' : added ? 'Added ✓' : 'Add to cart'}
          </button>
        </div>
      </div>
    </article>
  );
}
