/**
 * The single place where this app talks to the backend.
 *
 * Everything goes through `request()`, so there is exactly one implementation
 * of: building the URL, attaching the token, parsing the response, and turning
 * a failure into an Error the UI can display.
 */

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
).replace(/\/$/, '');

const TOKEN_STORAGE_KEY = 'mini-ecommerce-token';

/**
 * Is the API the one hosted on Render's free tier?
 *
 * Free Render services spin down after about 15 minutes of inactivity, and
 * the request that wakes one up can take the best part of a minute. That is
 * worth explaining to someone staring at a spinner — but only when it is
 * actually the explanation. Against a local backend, or anywhere else, a
 * slow request means something else entirely, and the app should stay quiet
 * rather than blame a host that is not involved.
 */
export const isRenderApi = (() => {
  try {
    // BASE_URL may be relative in some setups, hence the second argument.
    const { hostname } = new URL(BASE_URL, window.location.origin);
    return hostname === 'onrender.com' || hostname.endsWith('.onrender.com');
  } catch {
    return false;
  }
})();

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------
// localStorage keeps the user logged in across page reloads. It is read and
// written only through these three functions, so there is one place to change
// if the storage mechanism ever changes.

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    // Private-browsing modes can make localStorage throw.
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore: the app still works for this session, just not after a reload.
  }
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/**
 * An HTTP error with the parsed response body attached.
 *
 * `fieldErrors` holds DRF's per-field messages, e.g.
 * `{ quantity: ["Only 3 unit(s) ... are in stock."] }`, so a form can show
 * each message next to its input instead of dumping JSON on the page.
 */
export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }

  get fieldErrors() {
    if (!this.data || typeof this.data !== 'object') return {};
    const entries = Object.entries(this.data).filter(
      ([key]) => key !== 'detail',
    );
    return Object.fromEntries(entries);
  }
}

/** Turn a DRF error body into one readable sentence. */
function describeError(data, status) {
  if (!data) return `Request failed (HTTP ${status}).`;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;

  const messages = Object.entries(data).map(([field, value]) => {
    const text = Array.isArray(value) ? value.join(' ') : String(value);
    // non_field_errors is DRF's bucket for errors not tied to one input.
    return field === 'non_field_errors' ? text : `${field}: ${text}`;
  });

  return messages.join('\n') || `Request failed (HTTP ${status}).`;
}

// ---------------------------------------------------------------------------
// The request helper
// ---------------------------------------------------------------------------

/**
 * @param {string} path   path after /api, e.g. "/products/"
 * @param {object} options
 * @param {string} [options.method]  defaults to GET
 * @param {object|FormData} [options.body]  serialised as JSON, or sent as
 *   multipart when it is a FormData (file uploads)
 * @param {object} [options.params]  query string values (empty ones dropped)
 * @param {boolean} [options.auth]   send the stored token (default: true when
 *                                   one exists)
 */
export async function request(path, options = {}) {
  const { method = 'GET', body, params, auth = true, signal } = options;

  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      // Skip empty values so "?search=" never reaches the API.
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
  }

  // FormData is used for file uploads. The browser has to set
  // Content-Type itself in that case, because the header must carry the
  // multipart boundary — setting it by hand produces a request the server
  // cannot parse.
  const isUpload = typeof FormData !== 'undefined' && body instanceof FormData;

  const headers = {};
  if (body !== undefined && !isUpload) headers['Content-Type'] = 'application/json';

  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Token ${token}`;

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : isUpload ? body : JSON.stringify(body),
    signal,
  });

  // 204 No Content (logout, delete) has no body to parse.
  if (response.status === 204) return null;

  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    throw new ApiError(describeError(data, response.status), {
      status: response.status,
      data,
    });
  }

  return data;
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
};

export { BASE_URL };
