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
