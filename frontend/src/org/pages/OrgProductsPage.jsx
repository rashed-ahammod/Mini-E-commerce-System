/**
 * Catalog management: the product table, with stock, editing and deletion.
 *
 * The same `/api/products/` endpoint the shop reads from — the difference is
 * the token. Reading is public; writing requires an organization account,
 * which the server enforces, so a customer reaching this URL is redirected
 * by the route guard long before any of these buttons could be pressed.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import CatalogTabs from '../components/CatalogTabs';
import Modal from '../components/Modal';
import ProductFormModal from '../components/ProductFormModal';
import StockAdjustModal from '../components/StockAdjustModal';
import Pagination from '../../components/Pagination';
import { catalogAdminApi, categoryApi, productApi } from '../../api/endpoints';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { formatPrice } from '../../utils/format';

const PAGE_SIZE = 20;

export default function OrgProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(
    () => ({
      search: searchParams.get('search') || '',
      category: searchParams.get('category') || '',
      lowStock: searchParams.get('low_stock') || '',
      ordering: searchParams.get('ordering') || 'name',
      page: Number(searchParams.get('page') || 1),
    }),
    [searchParams],
  );

  const [searchInput, setSearchInput] = useState(filters.search);
  const debouncedSearch = useDebouncedValue(searchInput);

  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  // Which dialog is open, and for which product.
  const [editing, setEditing] = useState(null); // product | 'new'
  const [adjusting, setAdjusting] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [working, setWorking] = useState(false);

  const update = useCallback(
    (changes) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          Object.entries(changes).forEach(([key, value]) => {
            if (value === '' || value === null || value === false) next.delete(key);
            else next.set(key, String(value));
          });
          if (!('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (debouncedSearch !== filters.search) update({ search: debouncedSearch });
  }, [debouncedSearch, filters.search, update]);

  useEffect(() => {
    categoryApi
      .list({ page_size: 100, ordering: 'name' })
      .then((data) => setCategories(data.results))
      .catch(() => setCategories([]));
  }, []);

  const loadProducts = useCallback(
    (signal) => {
      setLoading(true);
      setError(null);
      return productApi
        .list(
          {
            search: filters.search,
            category: filters.category,
            low_stock: filters.lowStock,
            ordering: filters.ordering,
            page: filters.page,
            page_size: PAGE_SIZE,
          },
          { signal },
        )
        .then((data) => {
          setProducts(data.results);
          setCount(data.count);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === 'AbortError') return;
          if (err.status === 404 && filters.page > 1) {
            update({ page: 1 });
            return;
          }
          setError(err.message);
          setLoading(false);
        });
    },
    [filters, update],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadProducts(controller.signal);
    return () => controller.abort();
  }, [loadProducts]);

  // ---- actions -----------------------------------------------------------

  const saveProduct = async (payload) => {
    if (editing === 'new') {
      await catalogAdminApi.createProduct(payload);
      setNotice(`“${payload.name}” added to the catalog.`);
    } else {
      await catalogAdminApi.updateProduct(editing.id, payload);
      setNotice(`“${payload.name}” updated.`);
    }
    setEditing(null);
    loadProducts();
  };

  const saveStock = async (payload) => {
    const result = await catalogAdminApi.adjustStock(adjusting.id, payload);
    setNotice(
      `${result.product.name}: stock ${result.previous_stock} → ${result.new_stock}.`,
    );
    setAdjusting(null);
    loadProducts();
  };

  const confirmDelete = async () => {
    setWorking(true);
    setDeleteError(null);
    try {
      await catalogAdminApi.deleteProduct(deleting.id);
      setNotice(`“${deleting.name}” deleted.`);
      setDeleting(null);
      loadProducts();
    } catch (err) {
      // 409 is the server refusing to erase something an order points at.
      setDeleteError(
        err.status === 409
          ? `${err.message} Set its stock to 0 instead — the product stays, and the order history keeps its name.`
          : err.message,
      );
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Catalog</h1>
          <p className="muted">{count} products across {categories.length} categories.</p>
        </div>
        <button type="button" className="button" onClick={() => setEditing('new')}>
          Add a product
        </button>
      </header>

      <CatalogTabs />

      <form className="filter-row panel" onSubmit={(event) => event.preventDefault()}>
        <div className="field">
          <label htmlFor="search">Search</label>
          <input
            id="search"
            type="search"
            placeholder="name or description"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="category">Category</label>
          <select
            id="category"
            value={filters.category}
            onChange={(event) => update({ category: event.target.value })}
          >
            <option value="">All</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name} ({category.product_count})
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="low_stock">Stock at or below</label>
          <input
            id="low_stock"
            type="number"
            min="0"
            placeholder="any"
            value={filters.lowStock}
            onChange={(event) => update({ low_stock: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="ordering">Sort</label>
          <select
            id="ordering"
            value={filters.ordering}
            onChange={(event) => update({ ordering: event.target.value })}
          >
            <option value="name">Name</option>
            <option value="stock">Stock: lowest first</option>
            <option value="-stock">Stock: highest first</option>
            <option value="price">Price: low to high</option>
            <option value="-price">Price: high to low</option>
            <option value="-created_at">Newest first</option>
          </select>
        </div>
      </form>

      {notice && <p className="alert alert--success">{notice}</p>}
      {error && <p className="alert alert--error">{error}</p>}

      <section className="panel">
        <header className="panel__header">
          <h2>{loading ? 'Loading…' : `${count} product${count === 1 ? '' : 's'}`}</h2>
        </header>

        {loading ? (
          <p className="status" style={{ padding: 24 }}>Loading products…</p>
        ) : products.length === 0 ? (
          <div className="empty-state">
            <h3>No products match these filters</h3>
          </div>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Price</th>
                <th>Stock</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td className="table__product">
                    {product.image && <img src={product.image} alt="" loading="lazy" />}
                    <span>{product.name}</span>
                  </td>
                  <td className="muted">{product.category?.name}</td>
                  <td className="nums">{formatPrice(product.price)}</td>
                  <td>
                    <span
                      className={
                        product.stock === 0
                          ? 'pill pill--off'
                          : product.stock <= 5
                            ? 'pill pill--wait'
                            : 'pill pill--ok'
                      }
                    >
                      {product.stock === 0 ? 'Out of stock' : product.stock}
                    </span>
                  </td>
                  <td className="table__actions">
                    <button
                      type="button"
                      className="button button--ghost button--small"
                      onClick={() => setAdjusting(product)}
                    >
                      Adjust
                    </button>
                    <button
                      type="button"
                      className="button button--ghost button--small"
                      onClick={() => setEditing(product)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="button button--danger button--small"
                      onClick={() => {
                        setDeleting(product);
                        setDeleteError(null);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <Pagination
        page={filters.page}
        count={count}
        pageSize={PAGE_SIZE}
        onChange={(page) => {
          update({ page });
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
      />

      {editing && (
        <ProductFormModal
          product={editing === 'new' ? null : editing}
          categories={categories}
          onClose={() => setEditing(null)}
          onSave={saveProduct}
        />
      )}

      {adjusting && (
        <StockAdjustModal
          product={adjusting}
          onClose={() => setAdjusting(null)}
          onSave={saveStock}
        />
      )}

      {deleting && (
        <Modal
          title={`Delete ${deleting.name}?`}
          onClose={() => setDeleting(null)}
          footer={
            <>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDeleting(null)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="button button--danger-solid"
                onClick={confirmDelete}
                disabled={working}
              >
                {working ? 'Deleting…' : 'Delete'}
              </button>
            </>
          }
        >
          {deleteError ? (
            <p className="alert alert--error">{deleteError}</p>
          ) : (
            <p>
              This removes the product from the shop. If it has ever been
              ordered the server will refuse, so that the order history keeps
              its name.
            </p>
          )}
        </Modal>
      )}
    </div>
  );
}
