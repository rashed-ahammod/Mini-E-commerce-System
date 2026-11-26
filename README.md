# 🛒 Mini E-commerce System

A Mini E-commerce REST API built with **Django REST Framework**, plus a
**React** frontend that consumes it.

The API covers categories, products with filtering/searching/ordering/
pagination, token authentication and orders. The frontend is a small shop:
browse and filter the catalog, add things to a cart, log in, place orders and
look at your order history.

```
┌─────────────────────────┐        HTTP + token auth        ┌──────────────────────────┐
│  React frontend (Vite)  │ ──────────────────────────────▶ │  Django REST Framework   │
│  localhost:5173         │ ◀────────────────────────────── │  localhost:8000/api/     │
└─────────────────────────┘           JSON                  └───────────┬──────────────┘
                                                                        │
                                                            ┌───────────▼──────────────┐
                                                            │  SQLite (dev)            │
                                                            │  PostgreSQL (production) │
                                                            └──────────────────────────┘
```

## Repository layout

```
.
├── backend/        Django + DRF API        → backend/README.md
├── frontend/       React + Vite client     → frontend/README.md
├── postman/        Postman collection + environment
├── render.yaml     Render Blueprint for the API and its database
├── DEPLOYMENT.md   Render + Vercel deployment guide
└── README.md       you are here
```

Each half has its own README with the detail; this file is the overview and
the quick start.

## Quick start

Two terminals. **Backend first** — the frontend needs it running.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate              # Windows   (source .venv/bin/activate elsewhere)
pip install -r requirements.txt
copy .env.example .env              # cp on macOS/Linux
python manage.py migrate
python manage.py seed_data --demo-user
python manage.py runserver
```

- API: <http://127.0.0.1:8000/api/>
- Admin: <http://127.0.0.1:8000/admin/> (run `python manage.py createsuperuser` first)
- Demo login: **demo / demo12345**

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local        # cp on macOS/Linux
npm run dev
```

Open <http://localhost:5173>.

### 3. Tests

```bash
cd backend
python manage.py test               # 60 tests
```

## What is implemented

Everything the assignment asks for, plus two of the optional extras.

| Requirement | Where |
| --- | --- |
| Category API (create, list, retrieve, update, delete) | `catalog/views.py` → `CategoryViewSet` |
| Product API with name, description, price, stock, category, created date | `catalog/models.py`, `catalog/views.py` |
| Search by product name | `?search=` (SearchFilter) |
| Filter by category | `?category=`, `?category_name=` |
| Filter by price | `?price=`, `?min_price=`, `?max_price=` |
| Order by price | `?ordering=price` / `-price` |
| Pagination | `config/pagination.py`, applied to every list endpoint |
| Token authentication | `accounts/` — register, login, logout, me |
| Order API (create, list own, retrieve one) | `orders/` |
| Serializers, ModelViewSets, URL routing, model relationships | throughout |
| Postman collection for API testing | `postman/` |
| **Optional:** stock validation | `orders/serializers.py` |
| **Optional:** product image | `Product.image` |

Beyond the brief: 60 automated tests, a `seed_data` command, a React
frontend, and deployment configuration.

## API at a glance

Full tables, including every query parameter and status code, are in
[backend/README.md](backend/README.md).

| Method | Endpoint | Auth |
| --- | --- | --- |
| `GET` | `/api/` | — |
| `POST` | `/api/auth/register/` · `/api/auth/login/` | — |
| `POST` | `/api/auth/logout/` | token |
| `GET` | `/api/auth/me/` | token |
| `GET` | `/api/categories/` · `/api/categories/{id}/` | — |
| `POST` `PUT` `PATCH` `DELETE` | `/api/categories/…` | token |
| `GET` | `/api/products/` · `/api/products/{id}/` | — |
| `POST` `PUT` `PATCH` `DELETE` | `/api/products/…` | token |
| `POST` `GET` | `/api/orders/` · `/api/orders/{id}/` | token |

Reading the catalog is public; writing anything, and everything to do with
orders, needs a token:

```
Authorization: Token 9f2c1b7e0a4d...
```

Example requests:

```bash
curl "http://127.0.0.1:8000/api/products/?search=phone&ordering=price"
curl "http://127.0.0.1:8000/api/products/?category=1&min_price=100&max_price=500"

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo12345"}' | python -c "import json,sys;print(json.load(sys.stdin)['token'])")

curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

## Testing with Postman

Import both files from [`postman/`](postman), select the "Mini E-commerce -
Local" environment, and run **Auth / Login** once — a test script stores the
token, so every protected request then works.

No request has a hardcoded id (test scripts capture them), and the delete
requests only touch objects the collection itself created, so the whole
collection can be run top to bottom without destroying the seeded data.

## Decisions worth knowing

The things a reviewer is most likely to ask about:

- **Orders snapshot the price.** `Order.unit_price` records what the product
  cost when the order was placed, and `total_price` is derived from it on the
  server. Repricing a product never rewrites past orders, and a client cannot
  choose what it pays.
- **Ordered products cannot be deleted.** `Order.product` uses
  `on_delete=PROTECT`, so order history stays intact. The API turns the
  resulting database error into a **409** with a readable message rather than
  a 500.
- **Stock is validated twice** — once for a friendly message, once inside the
  transaction that decrements it, because another order can arrive in
  between.
- **Another user's order returns 404, not 403**, so order ids are not leaked.
- **The cart is client-side only.** The backend models one order as one
  product and one quantity, exactly as the assignment specifies, so checkout
  posts one order per cart line instead of inventing a cart API.

## Deployment

**Backend on Render, frontend on Vercel, PostgreSQL for the database.**
Step-by-step instructions are in **[DEPLOYMENT.md](DEPLOYMENT.md)**; the
short version:

| | Backend | Frontend |
| --- | --- | --- |
| Host | Render (web service) | Vercel (static) |
| Config in repo | [`render.yaml`](render.yaml), [`backend/render-build.sh`](backend/render-build.sh) | [`frontend/vercel.json`](frontend/vercel.json) |
| Root directory | `backend` | `frontend` |
| Must set | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS` | `VITE_API_BASE_URL` |

Deploy the backend first — the frontend needs its URL, which Vite inlines at
build time.

### The database

SQLite cannot be used in production: Render's filesystem is ephemeral, so the
file is wiped on every deploy. Use PostgreSQL via `DATABASE_URL` — the code
is identical either way.

- **Render Postgres (Free)** is created automatically by `render.yaml`, but
  **expires 30 days after creation** (then a 14-day grace period before the
  data is deleted).
- **Neon or Supabase (Free)** have no expiry, and are the better choice if a
  reviewer might open the link more than a month from now. Set
  `DJANGO_DB_CONN_MAX_AGE=0` for those, since they suspend when idle.

### Production behaviour

With `DJANGO_DEBUG=False` the app enables HTTPS redirects, secure cookies,
HSTS, nosniff and WhiteNoise's hashed static files — and **refuses to start**
if `DJANGO_SECRET_KEY` is still the development default, rather than serving
tokens anyone reading this repository could forge. It also picks up Render's
`RENDER_EXTERNAL_HOSTNAME` automatically, so the deployed URL never has to be
pasted into `ALLOWED_HOSTS` by hand. Verify a configuration with
`python manage.py check --deploy`.

### Free-tier caveats worth knowing

- A free Render service **sleeps after ~15 minutes idle**; the next request
  takes about 50 seconds while it wakes.
- **Uploaded product images do not survive a deploy** (ephemeral disk). The
  seeded catalog has no images, so this only matters if you upload some.

## Tech stack

| Backend | Frontend |
| --- | --- |
| Django 5.2 | React 19 |
| Django REST Framework 3.16 | Vite 7 |
| django-filter, django-cors-headers | React Router 7 |
| SQLite (dev) / PostgreSQL (prod) | plain CSS, no UI framework |
| gunicorn + WhiteNoise | — |
