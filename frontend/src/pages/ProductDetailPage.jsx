/** A single product, with a quantity picker that respects the stock. */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { productApi } from '../api/endpoints';
import { useCart } from '../cart/useCart';
import { formatDate, formatPrice } from '../utils/format';

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    productApi
      .get(id, { signal: controller.signal })
      .then((data) => {
        setProduct(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError(
          err.status === 404 ? 'This product does not exist.' : err.message,
        );
        setLoading(false);
      });

    return () => controller.abort();
  }, [id]);

  if (loading) return <p className="status">Loading product…</p>;

  if (error) {
    return (
      <div>
        <p className="alert alert--error">{error}</p>
        <Link to="/">← Back to products</Link>
      </div>
    );
  }

  const soldOut = !product.in_stock;

  const handleAdd = () => {
    addItem(product, quantity);
    setAdded(true);
  };

  return (
    <article className="product-detail">
      <Link to="/" className="product-detail__back">
        ← Back to products
      </Link>

      <div className="product-detail__grid">
        <div className="product-detail__image">
          {product.image ? (
            <img src={product.image} alt="" />
          ) : (
            <span className="product-card__placeholder" aria-hidden="true">
              {product.name.charAt(0)}
            </span>
          )}
        </div>

        <div>
          <p className="muted">{product.category?.name}</p>
          <h1>{product.name}</h1>
          <p className="product-detail__price">{formatPrice(product.price)}</p>

          <p className={soldOut ? 'product-card__stock is-out' : 'product-card__stock'}>
            {soldOut ? 'Out of stock' : `${product.stock} in stock`}
          </p>

          <p className="product-detail__description">
            {product.description || <span className="muted">No description.</span>}
          </p>

          {!soldOut && (
            <div className="product-detail__buy">
              <div className="field">
                <label htmlFor="quantity">Quantity</label>
                <input
                  id="quantity"
                  type="number"
                  min="1"
                  // Capped at the stock the API reported. The server checks
                  // again when the order is placed, so this is convenience,
                  // not the actual guard.
                  max={product.stock}
                  value={quantity}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setQuantity(
                      Math.max(1, Math.min(Number.isNaN(value) ? 1 : value, product.stock)),
                    );
                    setAdded(false);
                  }}
                />
              </div>

              <button type="button" className="button" onClick={handleAdd}>
                Add to cart
              </button>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => {
                  handleAdd();
                  navigate('/cart');
                }}
              >
                Buy now
              </button>
            </div>
          )}

          {added && (
            <p className="alert alert--success">
              Added to your cart. <Link to="/cart">Go to cart →</Link>
            </p>
          )}

          <dl className="product-detail__meta">
            <div>
              <dt>Product id</dt>
              <dd>{product.id}</dd>
            </div>
            <div>
              <dt>Added</dt>
              <dd>{formatDate(product.created_at)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </article>
  );
}
