# Frontend — Mini Shop

React 19 + Vite 7 + React Router 7, in plain JavaScript with no UI framework.
It consumes the Django REST API in [`../backend`](../backend).

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
├── components/          Layout, NavBar, ProtectedRoute, Pagination, ProductCard
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

### The catalog page

Every filter is applied by the **API**, not in the browser, and all of them
are stored in the URL query string. `/?search=phone&ordering=price&page=2` is
a shareable link, and the back button moves between filter states.

Two details worth knowing while debugging:

- the search box is debounced (350 ms) and in-flight requests are aborted when
  the filters change, so a slow response cannot overwrite a newer one;
- asking for a page past the end returns 404 from DRF, which the page catches
  and falls back to page 1 — that happens when you are on page 3 and then
  narrow the filters.

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
   `https://mini-ecommerce-api.onrender.com/api`.
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
VITE_API_BASE_URL=https://your-api.onrender.com/api npm run build
npm run preview
```

## Known choices you may want to change

- **Prices display as USD** via `Intl.NumberFormat('en-US', …)` in
  `utils/format.js`. The backend stores a plain decimal with no currency, so
  changing that one formatter changes the whole app.
- **Searching matches the description too**, because the backend's
  `search_fields` includes it. That is why `?search=phone` also returns
  "NoiseCancel Pro" — its description mentions headphones.
