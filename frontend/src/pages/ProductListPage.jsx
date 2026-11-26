/**
 * The catalog: search, category filter, price range, ordering and pagination.
 *
 * All of that work is done by the API, not in the browser — this page only
 * collects the inputs, puts them in the URL query string, and renders what
 * comes back. Keeping the filters in the URL means a filtered view can be
 * bookmarked, shared, and survives the back button.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import Pagination from '../components/Pagination';
import ProductCard from '../components/ProductCard';
import { categoryApi, productApi } from '../api/endpoints';
import { useDebouncedValue } from '../hooks/useDebouncedValue';

const PAGE_SIZE = 8;

const ORDERING_OPTIONS = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'price', label: 'Price: low to high' },
  { value: '-price', label: 'Price: high to low' },
  { value: 'name', label: 'Name: A to Z' },
];

export default function ProductListPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // The URL is the source of truth for the filters.
  const filters = useMemo(
    () => ({
      search: searchParams.get('search') || '',
      category: searchParams.get('category') || '',
      minPrice: searchParams.get('min_price') || '',
      maxPrice: searchParams.get('max_price') || '',
      inStock: searchParams.get('in_stock') === 'true',
      ordering: searchParams.get('ordering') || '-created_at',
      page: Number(searchParams.get('page') || 1),
    }),
    [searchParams],
  );

  // The search box is the one control that is not applied instantly, so it
  // keeps its own state and is pushed to the URL once typing pauses.
  const [searchInput, setSearchInput] = useState(filters.search);
  const debouncedSearch = useDebouncedValue(searchInput);

  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /** Write filters to the URL. Any change except paging returns to page 1. */
  const updateFilters = useCallback(
    (changes) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          Object.entries(changes).forEach(([key, value]) => {
            if (value === '' || value === null || value === false) {
              next.delete(key);
            } else {
              next.set(key, String(value));
            }
          });
          if (!('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  // Push the debounced search term into the URL.
  useEffect(() => {
    if (debouncedSearch !== filters.search) {
      updateFilters({ search: debouncedSearch });
    }
  }, [debouncedSearch, filters.search, updateFilters]);

  // Categories for the filter dropdown. page_size=100 so the dropdown is not
  // silently truncated by pagination.
  useEffect(() => {
    categoryApi
      .list({ page_size: 100, ordering: 'name' })
      .then((data) => setCategories(data.results))
      .catch(() => setCategories([])); // the rest of the page still works
  }, []);

  // Products, re-fetched whenever any filter changes.
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    productApi
      .list(
        {
          search: filters.search,
          category: filters.category,
          min_price: filters.minPrice,
          max_price: filters.maxPrice,
          in_stock: filters.inStock ? 'true' : '',
          ordering: filters.ordering,
          page: filters.page,
          page_size: PAGE_SIZE,
        },
        { signal: controller.signal },
      )
      .then((data) => {
        setProducts(data.results);
        setCount(data.count);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return; // a newer request replaced this one
        // Asking for a page past the end returns 404; fall back to page 1.
        if (err.status === 404 && filters.page > 1) {
          updateFilters({ page: 1 });
          return;
        }
        setError(err.message);
        setLoading(false);
      });

    return () => controller.abort();
  }, [filters, updateFilters]);

  const clearFilters = () => {
    setSearchInput('');
    setSearchParams({}, { replace: true });
  };

  const hasFilters =
    filters.search ||
    filters.category ||
    filters.minPrice ||
    filters.maxPrice ||
    filters.inStock;

  return (
    <div className="catalog">
      <header className="catalog__header">
        <h1>Products</h1>
        <p className="muted">
          Browse the catalog. Searching, filtering, sorting and paging are all
          done by the API.
        </p>
      </header>

      <form className="filters card" onSubmit={(event) => event.preventDefault()}>
        <div className="filters__row">
          <div className="field filters__search">
            <label htmlFor="search">Search</label>
            <input
              id="search"
              type="search"
              placeholder="e.g. phone"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="category">Category</label>
            <select
              id="category"
              value={filters.category}
              onChange={(event) => updateFilters({ category: event.target.value })}
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name} ({category.product_count})
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="ordering">Sort by</label>
            <select
              id="ordering"
              value={filters.ordering}
              onChange={(event) => updateFilters({ ordering: event.target.value })}
            >
              {ORDERING_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="filters__row">
          <div className="field">
            <label htmlFor="min_price">Min price</label>
            <input
              id="min_price"
              type="number"
              min="0"
              step="0.01"
              placeholder="0"
              value={filters.minPrice}
              onChange={(event) => updateFilters({ min_price: event.target.value })}
            />
          </div>

          <div className="field">
            <label htmlFor="max_price">Max price</label>
            <input
              id="max_price"
              type="number"
              min="0"
              step="0.01"
              placeholder="Any"
              value={filters.maxPrice}
              onChange={(event) => updateFilters({ max_price: event.target.value })}
            />
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={filters.inStock}
              onChange={(event) => updateFilters({ in_stock: event.target.checked })}
            />
            In stock only
          </label>

          {hasFilters && (
            <button
              type="button"
              className="button button--ghost button--small"
              onClick={clearFilters}
            >
              Clear filters
            </button>
          )}
        </div>
      </form>

      {error && <p className="alert alert--error">{error}</p>}

      {loading ? (
        <p className="status">Loading products…</p>
      ) : products.length === 0 ? (
        <p className="status">
          No products match these filters.{' '}
          {hasFilters && (
            <button type="button" className="link-button" onClick={clearFilters}>
              Clear them
            </button>
          )}
        </p>
      ) : (
        <>
          <p className="catalog__count muted">
            {count} product{count === 1 ? '' : 's'} found
          </p>
          <div className="product-grid">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </>
      )}

      <Pagination
        page={filters.page}
        count={count}
        pageSize={PAGE_SIZE}
        onChange={(page) => {
          updateFilters({ page });
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
      />
    </div>
  );
}
