# Frontend — Mini Shop

React 19 + Vite 7 + React Router 7, in plain JavaScript with no UI framework.
It consumes the Django REST API in [`../backend`](../backend).

**Deployed:** <https://mini-e-commerce-system-one.vercel.app> (Vercel), talking
to the API on Render. Sign in with `demo` / `demo12345`.

## Running it

The backend must be running first (see [../backend/README.md](../backend/README.md)).

```bash
cd frontend
npm install
copy .env.example .env.local      # cp on macOS/Linux
npm run dev
```

Open <http://localhost:5173>. Log in with the seeded demo account
(`demo` / `demo12345`) or create a new one.

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload on port 5173 |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the built `dist/` locally |
| `npm run lint` | ESLint over the whole project |

The dev server uses `strictPort`, so it fails rather than quietly moving to
another port — the backend's `CORS_ALLOWED_ORIGINS` lists 5173, and a silent
port change would produce CORS errors that are annoying to track down.

## Layout

```
frontend/src/
├── api/
│   ├── client.js        the only place that calls fetch
│   └── endpoints.js     every backend endpoint as a named function
├── auth/                AuthProvider, the context object, the useAuth hook
├── cart/                CartProvider, the context object, the useCart hook
├── components/          Layout, NavBar, ProtectedRoute, CatalogSidebar,
│                         Pagination, ProductCard, ProductCardSkeleton
├── org/                 the organization console (see below)
│   ├── OrganizationRoute.jsx
│   ├── components/      OrgLayout, Modal, StatusPill, CatalogTabs,
│   │                    ProductFormModal, StockAdjustModal
│   └── pages/           dashboard, orders, catalog, customers, accounts
├── hooks/               useDebouncedValue
├── pages/               one file per screen
├── utils/format.js      price and date formatting
├── styles/index.css     the whole stylesheet
├── App.jsx              routes
└── main.jsx             entry point and provider nesting
```

### How the layers fit together

- **No component contains a URL.** Pages call `productApi.list(...)` and the
  like; `endpoints.js` owns the paths, and `client.js` owns everything about
  how a request is made.
- **`client.js`** attaches the token, drops empty query values (so a cleared
  search box never sends `?search=`), handles `204 No Content`, and raises an
  `ApiError` carrying DRF's per-field messages as `error.fieldErrors` — which
  is how the register form can show a password rule under the password input.
- **`auth/`** keeps the token in `localStorage` and re-checks it against
  `/auth/me/` on startup, so a token invalidated elsewhere (or a reset
  development database) logs the user out instead of producing confusing 401s.

## Pages

| Route | Page | Needs login |
| --- | --- | --- |
| `/` | Catalog: search, category, price range, in-stock, sorting, pagination | no |
| `/products/:id` | Product details with a quantity picker | no |
| `/cart` | Cart and checkout | to check out |
| `/orders` | Order history | yes |
| `/orders/:id` | One order | yes |
| `/login`, `/register` | Authentication | no |
| `/org/*` | The organization console — see below | organization account |

### The catalog page

A sticky filter sidebar on the left, the product grid on the right.

[`CatalogSidebar.jsx`](src/components/CatalogSidebar.jsx) holds search,
category (with a product count beside each), price — four preset bands as
toggle chips plus min/max inputs — and an in-stock toggle. It is deliberately
presentational: it collects values and hands them up, so all the fetching
logic stays in [`ProductListPage.jsx`](src/pages/ProductListPage.jsx).

Sorting sits in a toolbar above the grid rather than in the sidebar, because
it is not a filter: it never changes how many results there are.

Every filter is applied by the **API**, not in the browser, and all of them
live in the URL query string. `/?search=laptop&category=2&ordering=price&page=2`
is a shareable link, and the back button moves between filter states.

Details worth knowing while debugging:

- the search box is debounced (350 ms) and in-flight requests are aborted when
  the filters change, so a slow response cannot overwrite a newer one;
- asking for a page past the end returns 404 from DRF, which the page catches
  and falls back to page 1 — that happens when you are on page 3 and then
  narrow the filters;
- below 860px the sidebar collapses behind a **Filters** button, because a
  fixed column would squeeze the grid down to one narrow card per row;
- while loading, the grid renders skeleton cards shaped like the real ones
  ([`ProductCardSkeleton.jsx`](src/components/ProductCardSkeleton.jsx)) so it
  does not jump when the data arrives;
- a product's picture comes from the API as a single `image` field. Cards
  fall back to a letter tile both when it is missing **and** when the image
  fails to load, so one dead link never leaves a hole in the grid.

### The organization console

A second area of the app at `/org`, for the people who **run** the shop
rather than shop in it. It is the same React application and the same token
— only the role differs.

| Route | Page | Needs |
| --- | --- | --- |
| `/org` | Dashboard: revenue, orders, best sellers, what needs attention | staff |
| `/org/orders` | The queue, filtered by status, customer, date, total | staff |
| `/org/orders/:id` | One order: history, and the actions that move it | staff |
| `/org/products` | Catalog: edit, restock, delete | staff |
| `/org/categories` | Categories | staff |
| `/org/customers` | Customers with spend and order counts | staff |
| `/org/customers/:id` | One customer, their orders, deactivation | staff |
| `/org/staff` | Organization accounts | **admin** |

Access is decided in one place,
[`OrganizationRoute.jsx`](src/org/OrganizationRoute.jsx), from the `role`
and `is_organization` that arrive with every login. A **customer** who
reaches one of these URLs is sent to the shop, not to the login page —
they are signed in perfectly well, just not as someone who runs the shop,
and asking them to log in again would be misleading. Anonymous visitors do
get the login page.

The console is styled to look unlike the shop — dark rail, own navigation,
a visible "Operations console" label. Someone who can both shop and run the
shop should never be in doubt about which one they are looking at; that is
what stops a test order being cancelled for real.

#### The rules live on the server

Two places where it would have been easy, and wrong, to keep a copy:

- **Order statuses.** The status tabs come from
  `GET /org/orders/statuses/`, and the buttons on an order come from that
  order's own `next_statuses`. Nothing in the frontend knows that
  *confirmed* follows *pending*. Add a status on the backend and the console
  offers it with no change here; a hard-coded copy would have drifted the
  first time the rules moved.
- **Lockout guards.** The server refuses to let an admin change their own
  role or deactivate their own account. The accounts page does not
  re-implement that — it simply does not draw those buttons on your own row,
  and says why. The server is still what enforces it.

#### Actions that need a reason

Cancelling an order, deactivating a customer and revoking a colleague's
access all open a dialog rather than firing from a button, and the confirm
stays disabled until the reason is typed, because the API requires one.
Each dialog states what will actually happen — how many units return to
which product, that a customer's orders are untouched, that the person is
signed out immediately.

#### Stock

The product edit form shows stock **read-only**. Writing it back from a form
would undo any sale made while the form was open. The adjust dialog offers
*Received* and *Removed*, which send a delta the server applies under a row
lock, and *Stocktake*, which sends an absolute count and carries a warning
that it overwrites.

### The cart

The backend has **no cart**: one order is one product and one quantity, as the
assignment specifies. The cart is therefore client-side only (persisted to
`localStorage`), and checkout posts **one order per line, sequentially** —
each order changes the stock the next one is validated against, so running
them in parallel would make the result depend on timing.

That means a checkout can partly succeed. Rather than hide it, the page
removes the lines that were ordered, keeps the ones that failed with the
server's own message beside them, and reports how many of each.

## Deployment (Vercel)

The build output in `dist/` is static files. Full instructions, including the
Render backend, are in [../DEPLOYMENT.md](../DEPLOYMENT.md).

1. Vercel → **Add New → Project** → import the repository.
2. **Set Root Directory to `frontend`.** Without it the build fails, because
   `package.json` is not at the repository root. Framework, build command and
   output directory come from [`vercel.json`](vercel.json).
3. Add the environment variable `VITE_API_BASE_URL`, pointing at the deployed
   Render API with `/api` and no trailing slash, e.g.
   `https://mini-ecommerce-api-alnq.onrender.com/api`.
4. After deploying, add the Vercel URL to `CORS_ALLOWED_ORIGINS` on the
   backend, or the browser blocks every request.

Two things that catch people out:

- **`VITE_API_BASE_URL` is inlined at build time**, not read at run time.
  Changing it in Vercel does nothing until you redeploy.
- **Preview deployments get a new URL per commit**, so they fail CORS unless
  the backend also sets `CORS_ALLOWED_ORIGIN_REGEXES` to a pattern scoped to
  your project name.

`vercel.json` rewrites every unmatched path to `index.html` — so refreshing
`/products/3` works instead of returning 404 — and caches the hashed files
under `/assets/` permanently.

Check a production build locally before pushing:

```bash
VITE_API_BASE_URL=https://mini-ecommerce-api-alnq.onrender.com/api npm run build
npm run preview
```

## Known choices you may want to change

- **Prices display as USD** via `Intl.NumberFormat('en-US', …)` in
  `utils/format.js`. The backend stores a plain decimal with no currency, so
  changing that one formatter changes the whole app.
- **Searching matches the description too**, because the backend's
  `search_fields` includes it. That is why `?search=phone` returns 23
  products rather than the handful whose *names* contain "phone" — "Oppo
  A57" and "Realme XT" match because their descriptions mention a phone.
  To match names only, drop `"description"` from `search_fields` in
  `catalog/views.py`.
