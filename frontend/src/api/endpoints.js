/**
 * Every backend endpoint this app uses, in one file.
 *
 * Components import these functions instead of writing URLs, so a change to a
 * path or a query parameter happens here and nowhere else.
 */

import { api } from './client';

// ---- auth -----------------------------------------------------------------

export const authApi = {
  /** POST /auth/register/ -> { token, user } */
  register: ({ username, email, password }) =>
    api.post('/auth/register/', { username, email, password }, { auth: false }),

  /** POST /auth/login/ -> { token, user } */
  login: ({ username, password }) =>
    api.post('/auth/login/', { username, password }, { auth: false }),

  /** POST /auth/logout/ -> 204, the token is destroyed server-side */
  logout: () => api.post('/auth/logout/'),

  /** GET /auth/me/ -> the user the stored token belongs to */
  me: () => api.get('/auth/me/'),
};

// ---- catalog --------------------------------------------------------------

export const categoryApi = {
  /** GET /categories/ -> { count, next, previous, results } */
  list: (params) => api.get('/categories/', { params, auth: false }),

  get: (id) => api.get(`/categories/${id}/`, { auth: false }),
};

export const productApi = {
  /**
   * GET /products/
   * @param {object} params any of: search, category, min_price, max_price,
   *   in_stock, ordering, page, page_size. Empty values are dropped by the
   *   client, so passing the whole filter state is safe.
   */
  list: (params, options) => api.get('/products/', { params, auth: false, ...options }),

  get: (id, options) => api.get(`/products/${id}/`, { auth: false, ...options }),
};

// ---- orders ---------------------------------------------------------------

export const orderApi = {
  /** POST /orders/ — the user comes from the token, prices from the server */
  create: ({ productId, quantity }) =>
    api.post('/orders/', { product_id: productId, quantity }),

  /** GET /orders/ -> the logged-in user's orders, newest first */
  list: (params) => api.get('/orders/', { params }),

  get: (id) => api.get(`/orders/${id}/`),
};

// ---- organization ---------------------------------------------------------
// Everything the people who run the shop use. These all answer 403 to a
// customer's token, which is why the UI gates them on `user.is_organization`
// rather than discovering it from a failed request.

export const orgApi = {
  /** GET /org/dashboard/ — the whole shop in one request. */
  dashboard: (params, options) => api.get('/org/dashboard/', { params, ...options }),

  orders: {
    /**
     * GET /org/orders/ — every customer's orders.
     * @param {object} params status, status__in, open, customer,
     *   customer_username, product, placed_after, placed_before, min_total,
     *   max_total, search, ordering, page, page_size
     */
    list: (params, options) => api.get('/org/orders/', { params, ...options }),

    get: (id, options) => api.get(`/org/orders/${id}/`, options),

    /** GET /org/orders/statuses/ — the workflow, so the UI need not copy it. */
    statuses: (options) => api.get('/org/orders/statuses/', options),

    /** POST /org/orders/{id}/status/ — advance the order. */
    setStatus: (id, { status, note }) =>
      api.post(`/org/orders/${id}/status/`, { status, note }),

    /** POST /org/orders/{id}/cancel/ — cancel, returning the stock. */
    cancel: (id, { reason }) => api.post(`/org/orders/${id}/cancel/`, { reason }),
  },

  customers: {
    list: (params, options) => api.get('/org/customers/', { params, ...options }),
    get: (id, options) => api.get(`/org/customers/${id}/`, options),
    deactivate: (id, { reason }) =>
      api.post(`/org/customers/${id}/deactivate/`, { reason }),
    activate: (id) => api.post(`/org/customers/${id}/activate/`, {}),
  },

  /** Organization accounts. Admin-only: staff receive 403. */
  staff: {
    list: (params, options) => api.get('/org/staff/', { params, ...options }),
    get: (id, options) => api.get(`/org/staff/${id}/`, options),
    create: (details) => api.post('/org/staff/', details),
    update: (id, changes) => api.patch(`/org/staff/${id}/`, changes),
    deactivate: (id, { reason }) =>
      api.post(`/org/staff/${id}/deactivate/`, { reason }),
    activate: (id) => api.post(`/org/staff/${id}/activate/`, {}),
  },
};

// ---- catalog writes (organization only) -----------------------------------
// These live on the public catalog endpoints but require an organization
// account, so they are grouped here rather than on productApi/categoryApi,
// where a customer-facing component might reach for them by mistake.

export const catalogAdminApi = {
  createCategory: (details) => api.post('/categories/', details),
  updateCategory: (id, changes) => api.patch(`/categories/${id}/`, changes),
  deleteCategory: (id) => api.delete(`/categories/${id}/`),

  createProduct: (details) => api.post('/products/', details),
  updateProduct: (id, changes) => api.patch(`/products/${id}/`, changes),
  deleteProduct: (id) => api.delete(`/products/${id}/`),

  /**
   * POST /products/{id}/adjust-stock/
   * Send `delta` for a relative change or `stock` for an absolute count —
   * one or the other, never both. Prefer `delta`: it is applied to the row
   * under the same lock the order path uses, so a sale landing between
   * reading the page and submitting is not overwritten.
   */
  adjustStock: (id, { delta, stock, reason }) =>
    api.post(`/products/${id}/adjust-stock/`, { delta, stock, reason }),
};
