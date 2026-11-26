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
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setImageFailed(false);
    setQuantity(1);
    setAdded(false);

    productApi
      .get(id, { signal: controller.signal })
      .then((data) => {
        setProduct(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setError(err.status === 404 ? 'This product does not exist.' : err.message);
        setLoading(false);
      });

    return () => controller.abort();
  }, [id]);

  if (loading) {
    return (
      <div className="product-detail">
        <div className="product-detail__grid">
          <div className="skeleton product-detail__media" />
          <div>
            <div className="skeleton skeleton--line skeleton--short" />
            <div className="skeleton skeleton--line skeleton--title" />
            <div className="skeleton skeleton--line skeleton--medium" />
            <div className="skeleton skeleton--line" />
            <div className="skeleton skeleton--line" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state card">
        <h3>{error}</h3>
        <Link to="/" className="button">
          Back to products
        </Link>
      </div>
    );
  }

  const soldOut = !product.in_stock;
  const lowStock = product.in_stock && product.stock <= 5;
  const showImage = product.image && !imageFailed;

  const handleAdd = () => {
    addItem(product, quantity);
    setAdded(true);
  };

  return (
    <article className="product-detail">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link to="/">Products</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/?category=${product.category?.id}`}>{product.category?.name}</Link>
        <span aria-hidden="true">/</span>
        <span className="muted">{product.name}</span>
      </nav>

      <div className="product-detail__grid">
        <div className="product-detail__media">
          {showImage ? (
            <img
              src={product.image}
              alt={product.name}
              onError={() => setImageFailed(true)}
            />
          ) : (
            <span className="product-card__placeholder" aria-hidden="true">
              {product.name.charAt(0)}
            </span>
          )}
        </div>

        <div className="product-detail__info">
          <p className="product-card__category">{product.category?.name}</p>
          <h1>{product.name}</h1>

          <p className="product-detail__price">{formatPrice(product.price)}</p>

          <p className="product-detail__stock">
            {soldOut ? (
              <span className="tag tag--muted">Out of stock</span>
            ) : lowStock ? (
              <span className="tag tag--warn">Only {product.stock} left</span>
            ) : (
              <span className="tag tag--ok">In stock · {product.stock} available</span>
            )}
          </p>

          <p className="product-detail__description">
            {product.description || <span className="muted">No description.</span>}
          </p>

          {!soldOut && (
            <div className="product-detail__buy">
              <div className="quantity">
                <button
                  type="button"
                  className="quantity__step"
                  onClick={() => {
                    setQuantity((q) => Math.max(1, q - 1));
                    setAdded(false);
                  }}
                  disabled={quantity <= 1}
                  aria-label="Decrease quantity"
                >
                  −
                </button>
                <input
                  type="number"
                  min="1"
                  // Capped at the stock the API reported. The server checks
                  // again when the order is placed, so this is convenience,
                  // not the actual guard.
                  max={product.stock}
                  value={quantity}
                  aria-label="Quantity"
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setQuantity(
                      Math.max(
                        1,
                        Math.min(Number.isNaN(value) ? 1 : value, product.stock),
                      ),
                    );
                    setAdded(false);
                  }}
                />
                <button
                  type="button"
                  className="quantity__step"
                  onClick={() => {
                    setQuantity((q) => Math.min(product.stock, q + 1));
                    setAdded(false);
                  }}
                  disabled={quantity >= product.stock}
                  aria-label="Increase quantity"
                >
                  +
                </button>
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

          {!soldOut && (
            <p className="product-detail__subtotal muted">
              Subtotal:{' '}
              <strong>{formatPrice(Number(product.price) * quantity)}</strong>
            </p>
          )}

          {added && (
            <p className="alert alert--success">
              Added to your cart. <Link to="/cart">Go to cart →</Link>
            </p>
          )}

          <dl className="product-detail__meta">
            <div>
              <dt>Product id</dt>
              <dd>#{product.id}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{product.category?.name}</dd>
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
