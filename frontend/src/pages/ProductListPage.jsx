/**
 * The catalog: a filter sidebar on the left, the product grid on the right.
 *
 * Searching, filtering, sorting and paging are all done by the API — this
 * page only collects the inputs, writes them to the URL query string, and
 * renders what comes back. Keeping the filters in the URL means a filtered
 * view can be bookmarked, shared, and survives the back button.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import CatalogSidebar from '../components/CatalogSidebar';
import Pagination from '../components/Pagination';
import ProductCard from '../components/ProductCard';
import ProductCardSkeleton from '../components/ProductCardSkeleton';
import { categoryApi, productApi } from '../api/endpoints';
import { useDebouncedValue } from '../hooks/useDebouncedValue';

const PAGE_SIZE = 9;

const ORDERING_OPTIONS = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'price', label: 'Price: low to high' },
  { value: '-price', label: 'Price: high to low' },
  { value: 'name', label: 'Name: A to Z' },
  { value: '-stock', label: 'Best stocked' },
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

  // The search box is the one control not applied instantly: it keeps its own
  // state and is pushed to the URL once typing pauses.
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

  // Categories for the sidebar. page_size=100 so the list is not silently
  // truncated by pagination.
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

  const clearFilters = useCallback(() => {
    setSearchInput('');
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  // Ordering is not counted: it is always set to something.
  const activeFilters = [
    filters.search,
    filters.category,
    filters.minPrice,
    filters.maxPrice,
    filters.inStock,
  ].filter(Boolean).length;

  const activeCategory = categories.find(
    (category) => String(category.id) === String(filters.category),
  );

  return (
    <div className="catalog">
      <header className="catalog__hero">
        <div>
          <h1>
            {activeCategory ? activeCategory.name : 'All products'}
          </h1>
          <p className="muted">
            {activeCategory
              ? activeCategory.description || 'Browse this category.'
              : 'Phones, laptops, tablets and accessories.'}
          </p>
        </div>
      </header>

      <div className="catalog__layout">
        <CatalogSidebar
          categories={categories}
          filters={filters}
          searchInput={searchInput}
          onSearchChange={setSearchInput}
          onChange={updateFilters}
          onClear={clearFilters}
          activeCount={activeFilters}
          resultCount={count}
        />

        <div className="catalog__main">
          <div className="catalog__toolbar">
            <p className="catalog__count">
              {loading ? (
                'Loading…'
              ) : (
                <>
                  <strong>{count}</strong> product{count === 1 ? '' : 's'}
                  {activeFilters > 0 && ' matching your filters'}
                </>
              )}
            </p>

            <div className="catalog__sort">
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

          {error && <p className="alert alert--error">{error}</p>}

          {loading ? (
            <div className="product-grid">
              {Array.from({ length: PAGE_SIZE }, (_, index) => (
                <ProductCardSkeleton key={index} />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="empty-state card">
              <h3>No products match these filters</h3>
              <p className="muted">
                Try a different search term, or widen the price range.
              </p>
              {activeFilters > 0 && (
                <button type="button" className="button" onClick={clearFilters}>
                  Clear all filters
                </button>
              )}
            </div>
          ) : (
            <div className="product-grid">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
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
      </div>
    </div>
  );
}
