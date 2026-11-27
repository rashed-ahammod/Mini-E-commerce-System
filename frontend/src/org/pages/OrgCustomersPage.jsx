/**
 * The customer list.
 *
 * Two figures sit side by side and are easy to confuse, so the column
 * headers spell out the difference: `orders` counts every order they have
 * placed, including cancelled ones, while `spent` counts only what was not
 * cancelled. They answer different questions — how often someone buys, and
 * what the shop actually took.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import Pagination from '../../components/Pagination';
import { orgApi } from '../../api/endpoints';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { formatDate, formatPrice } from '../../utils/format';

const PAGE_SIZE = 20;

export default function OrgCustomersPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(
    () => ({
      search: searchParams.get('search') || '',
      hasOrders: searchParams.get('has_orders') || '',
      isActive: searchParams.get('is_active') || '',
      ordering: searchParams.get('ordering') || '-date_joined',
      page: Number(searchParams.get('page') || 1),
    }),
    [searchParams],
  );

  const [searchInput, setSearchInput] = useState(filters.search);
  const debouncedSearch = useDebouncedValue(searchInput);

  const [customers, setCustomers] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    orgApi.customers
      .list(
        {
          search: filters.search,
          has_orders: filters.hasOrders,
          is_active: filters.isActive,
          ordering: filters.ordering,
          page: filters.page,
          page_size: PAGE_SIZE,
        },
        { signal: controller.signal },
      )
      .then((data) => {
        setCustomers(data.results);
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

    return () => controller.abort();
  }, [filters, update]);

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Customers</h1>
          <p className="muted">
            People who shop here. Organization accounts are managed separately.
          </p>
        </div>
      </header>

      <form className="filter-row panel" onSubmit={(event) => event.preventDefault()}>
        <div className="field">
          <label htmlFor="search">Search</label>
          <input
            id="search"
            type="search"
            placeholder="username or email"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="has_orders">Activity</label>
          <select
            id="has_orders"
            value={filters.hasOrders}
            onChange={(event) => update({ has_orders: event.target.value })}
          >
            <option value="">Everyone</option>
            <option value="true">Has ordered</option>
            <option value="false">Never ordered</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="is_active">Account</label>
          <select
            id="is_active"
            value={filters.isActive}
            onChange={(event) => update({ is_active: event.target.value })}
          >
            <option value="">Any</option>
            <option value="true">Active</option>
            <option value="false">Deactivated</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="ordering">Sort</label>
          <select
            id="ordering"
            value={filters.ordering}
            onChange={(event) => update({ ordering: event.target.value })}
          >
            <option value="-date_joined">Newest first</option>
            <option value="-total_spent">Highest spend</option>
            <option value="-order_count">Most orders</option>
            <option value="-last_order_at">Most recent order</option>
            <option value="username">Username</option>
          </select>
        </div>
      </form>

      {error && <p className="alert alert--error">{error}</p>}

      <section className="panel">
        <header className="panel__header">
          <h2>{loading ? 'Loading…' : `${count} customer${count === 1 ? '' : 's'}`}</h2>
        </header>

        {loading ? (
          <p className="status" style={{ padding: 24 }}>Loading customers…</p>
        ) : customers.length === 0 ? (
          <div className="empty-state">
            <h3>No customers match these filters</h3>
          </div>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Customer</th>
                <th title="Every order, including cancelled ones">Orders</th>
                <th title="Excludes cancelled orders">Spent</th>
                <th>Last order</th>
                <th>Joined</th>
                <th>Account</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr key={customer.id}>
                  <td>
                    <Link to={`/org/customers/${customer.id}`} className="table__link">
                      {customer.username}
                    </Link>
                    {customer.email && (
                      <div className="muted table__sub">{customer.email}</div>
                    )}
                  </td>
                  <td className="nums">{customer.order_count}</td>
                  <td className="nums">{formatPrice(customer.total_spent)}</td>
                  <td className="muted">
                    {customer.last_order_at ? formatDate(customer.last_order_at) : '—'}
                  </td>
                  <td className="muted">{formatDate(customer.date_joined)}</td>
                  <td>
                    <span className={customer.is_active ? 'pill pill--ok' : 'pill pill--off'}>
                      {customer.is_active ? 'Active' : 'Deactivated'}
                    </span>
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
    </div>
  );
}
