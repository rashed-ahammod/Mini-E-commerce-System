/**
 * The catalog's filter sidebar.
 *
 * Every control here maps to a query parameter the API understands; this
 * component only collects values and hands them up. It is deliberately
 * presentational so the page keeps all the fetching logic in one place.
 *
 * On narrow screens the whole panel collapses behind a "Filters" button,
 * because a fixed sidebar would push the product grid off the screen.
 */

import { useState } from 'react';

const PRICE_PRESETS = [
  { label: 'Under $50', min: '', max: '50' },
  { label: '$50 – $200', min: '50', max: '200' },
  { label: '$200 – $800', min: '200', max: '800' },
  { label: 'Over $800', min: '800', max: '' },
];

export default function CatalogSidebar({
  categories,
  filters,
  searchInput,
  onSearchChange,
  onChange,
  onClear,
  activeCount,
  resultCount,
}) {
  const [open, setOpen] = useState(false);

  const isActivePreset = (preset) =>
    filters.minPrice === preset.min && filters.maxPrice === preset.max;

  const applyPreset = (preset) => {
    if (isActivePreset(preset)) {
      onChange({ min_price: '', max_price: '' });
    } else {
      onChange({ min_price: preset.min, max_price: preset.max });
    }
  };

  return (
    <>
      <button
        type="button"
        className="button button--ghost sidebar__toggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        {open ? 'Hide filters' : 'Filters'}
        {activeCount > 0 && <span className="badge">{activeCount}</span>}
      </button>

      <aside className={`sidebar ${open ? 'is-open' : ''}`}>
        <div className="sidebar__header">
          <h2>Filters</h2>
          {activeCount > 0 && (
            <button type="button" className="link-button" onClick={onClear}>
              Clear all
            </button>
          )}
        </div>

        {/* ---- search ---- */}
        <section className="sidebar__section">
          <label htmlFor="search">Search</label>
          <div className="sidebar__search">
            <svg viewBox="0 0 20 20" aria-hidden="true" className="sidebar__search-icon">
              <path
                d="M9 3a6 6 0 104.47 10.03l3.25 3.25 1.06-1.06-3.25-3.25A6 6 0 009 3zm0 1.5a4.5 4.5 0 110 9 4.5 4.5 0 010-9z"
                fill="currentColor"
              />
            </svg>
            <input
              id="search"
              type="search"
              placeholder="Search products…"
              value={searchInput}
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </div>
          <p className="sidebar__hint">Matches names and descriptions.</p>
        </section>

        {/* ---- category ---- */}
        <section className="sidebar__section">
          <h3>Category</h3>
          <ul className="sidebar__list">
            <li>
              <button
                type="button"
                className={`sidebar__option ${!filters.category ? 'is-active' : ''}`}
                onClick={() => onChange({ category: '' })}
              >
                <span>All categories</span>
              </button>
            </li>
            {categories.map((category) => (
              <li key={category.id}>
                <button
                  type="button"
                  className={`sidebar__option ${
                    String(filters.category) === String(category.id) ? 'is-active' : ''
                  }`}
                  onClick={() =>
                    onChange({
                      // Clicking the active category clears it, which saves a
                      // trip back to "All categories".
                      category:
                        String(filters.category) === String(category.id)
                          ? ''
                          : category.id,
                    })
                  }
                >
                  <span>{category.name}</span>
                  <span className="sidebar__count">{category.product_count}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* ---- price ---- */}
        <section className="sidebar__section">
          <h3>Price</h3>
          <div className="sidebar__presets">
            {PRICE_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className={`chip ${isActivePreset(preset) ? 'is-active' : ''}`}
                onClick={() => applyPreset(preset)}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="sidebar__range">
            <div className="field">
              <label htmlFor="min_price">Min</label>
              <input
                id="min_price"
                type="number"
                min="0"
                step="0.01"
                placeholder="0"
                value={filters.minPrice}
                onChange={(event) => onChange({ min_price: event.target.value })}
              />
            </div>
            <span className="sidebar__range-dash" aria-hidden="true">
              –
            </span>
            <div className="field">
              <label htmlFor="max_price">Max</label>
              <input
                id="max_price"
                type="number"
                min="0"
                step="0.01"
                placeholder="Any"
                value={filters.maxPrice}
                onChange={(event) => onChange({ max_price: event.target.value })}
              />
            </div>
          </div>
        </section>

        {/* ---- availability ---- */}
        <section className="sidebar__section">
          <h3>Availability</h3>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={filters.inStock}
              onChange={(event) => onChange({ in_stock: event.target.checked })}
            />
            In stock only
          </label>
        </section>

        <p className="sidebar__result-count">
          {resultCount} product{resultCount === 1 ? '' : 's'} match
        </p>
      </aside>
    </>
  );
}
