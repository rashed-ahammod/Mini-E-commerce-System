/**
 * The order queue: every customer's orders, filtered and worked through.
 *
 * The status tabs are built from `GET /org/orders/statuses/` rather than a
 * list in this file. The server owns the workflow; a copy here would drift
 * the first time a status is added, and the UI would quietly stop offering
 * it.
 *
 * Filters live in the URL so a view — "pending orders over $500 this week" —
 * can be bookmarked, shared with a colleague, and survives the back button.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import Pagination from '../../components/Pagination';
import StatusPill from '../components/StatusPill';
import { orgApi } from '../../api/endpoints';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { formatDate, formatPrice } from '../../utils/format';

const PAGE_SIZE = 20;

const SORTS = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'created_at', label: 'Oldest first' },
  { value: '-total_price', label: 'Largest first' },
  { value: 'status', label: 'By status' },
];

export default function OrgOrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(
    () => ({
      status: searchParams.get('status') || '',
      open: searchParams.get('open') || '',
      search: searchParams.get('search') || '',
      customer: searchParams.get('customer_username') || '',
      placedAfter: searchParams.get('placed_after') || '',
      minTotal: searchParams.get('min_total') || '',
      ordering: searchParams.get('ordering') || '-created_at',
      page: Number(searchParams.get('page') || 1),
    }),
    [searchParams],
  );

  const [searchInput, setSearchInput] = useState(filters.search);
  const debouncedSearch = useDebouncedValue(searchInput);

  const [workflow, setWorkflow] = useState([]);
  const [orders, setOrders] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const update = useCallback(
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

  useEffect(() => {
    if (debouncedSearch !== filters.search) {
      update({ search: debouncedSearch });
    }
  }, [debouncedSearch, filters.search, update]);

  // The workflow, for the tab labels.
  useEffect(() => {
    orgApi.orders
      .statuses()
      .then(setWorkflow)
      .catch(() => setWorkflow([])); // tabs degrade to "All" and "Open"
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    orgApi.orders
      .list(
        {
          status: filters.status,
          open: filters.open,
          search: filters.search,
          customer_username: filters.customer,
          placed_after: filters.placedAfter,
          min_total: filters.minTotal,
          ordering: filters.ordering,
          page: filters.page,
          page_size: PAGE_SIZE,
        },
        { signal: controller.signal },
      )
      .then((data) => {
        setOrders(data.results);
        setCount(data.count);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        // Narrowing the filters while on a later page asks for a page that
        // no longer exists; fall back rather than showing an error.
        if (err.status === 404 && filters.page > 1) {
          update({ page: 1 });
          return;
        }
        setError(err.message);
        setLoading(false);
      });

    return () => controller.abort();
  }, [filters, update]);

  const clear = () => {
    setSearchInput('');
    setSearchParams({}, { replace: true });
  };

  const activeFilters = [
    filters.status,
    filters.open,
    filters.search,
    filters.customer,
    filters.placedAfter,
    filters.minTotal,
  ].filter(Boolean).length;

  const selectTab = (tab) => {
    // "All" and "Open" are not statuses, so they clear the status filter.
    if (tab === 'all') return update({ status: '', open: '' });
    if (tab === 'open') return update({ status: '', open: 'true' });
    return update({ status: tab, open: '' });
  };

  const activeTab = filters.status || (filters.open === 'true' ? 'open' : 'all');

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Orders</h1>
          <p className="muted">Every customer's orders, newest first.</p>
        </div>
      </header>

      {/* ---- status tabs, built from the server's workflow ---- */}
      <nav className="tabs" aria-label="Filter by status">
        <button
          type="button"
          className={activeTab === 'all' ? 'is-active' : ''}
          onClick={() => selectTab('all')}
        >
          All
        </button>
        <button
          type="button"
          className={activeTab === 'open' ? 'is-active' : ''}
          onClick={() => selectTab('open')}
        >
          Open
        </button>
        {workflow.map((entry) => (
          <button
            key={entry.status}
            type="button"
            className={activeTab === entry.status ? 'is-active' : ''}
            onClick={() => selectTab(entry.status)}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      {/* ---- the rest of the filters ---- */}
      <form className="filter-row panel" onSubmit={(event) => event.preventDefault()}>
        <div className="field">
          <label htmlFor="search">Search</label>
          <input
            id="search"
            type="search"
            placeholder="product, username or email"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="customer">Customer</label>
          <input
            id="customer"
            type="text"
            placeholder="exact username"
            value={filters.customer}
            onChange={(event) => update({ customer_username: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="placed_after">Placed on or after</label>
          <input
            id="placed_after"
            type="date"
            value={filters.placedAfter}
            onChange={(event) => update({ placed_after: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="min_total">Min total</label>
          <input
            id="min_total"
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={filters.minTotal}
            onChange={(event) => update({ min_total: event.target.value })}
          />
        </div>

        <div className="field">
          <label htmlFor="ordering">Sort</label>
          <select
            id="ordering"
            value={filters.ordering}
            onChange={(event) => update({ ordering: event.target.value })}
          >
            {SORTS.map((sort) => (
              <option key={sort.value} value={sort.value}>
                {sort.label}
              </option>
            ))}
          </select>
        </div>

        {activeFilters > 0 && (
          <button type="button" className="button button--ghost button--small" onClick={clear}>
            Clear ({activeFilters})
          </button>
        )}
      </form>

      {error && <p className="alert alert--error">{error}</p>}

      <section className="panel">
        <header className="panel__header">
          <h2>{loading ? 'Loading…' : `${count} order${count === 1 ? '' : 's'}`}</h2>
        </header>

        {loading ? (
          <p className="status" style={{ padding: 24 }}>
            Loading orders…
          </p>
        ) : orders.length === 0 ? (
          <div className="empty-state">
            <h3>No orders match these filters</h3>
            {activeFilters > 0 && (
              <button type="button" className="button" onClick={clear}>
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Order</th>
                <th>Customer</th>
                <th>Product</th>
                <th>Qty</th>
                <th>Total</th>
                <th>Status</th>
                <th>Placed</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>
                    <Link to={`/org/orders/${order.id}`} className="table__link">
                      #{order.id}
                    </Link>
                  </td>
                  <td>{order.customer.username}</td>
                  <td className="table__product">
                    {order.product.image && (
                      <img src={order.product.image} alt="" loading="lazy" />
                    )}
                    <span>{order.product.name}</span>
                  </td>
                  <td>{order.quantity}</td>
                  <td className="nums">{formatPrice(order.total_price)}</td>
                  <td>
                    <StatusPill status={order.status} label={order.status_display} />
                  </td>
                  <td className="muted">{formatDate(order.created_at)}</td>
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
    </div>
  );
}
