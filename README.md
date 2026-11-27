# 🛒 Mini E-commerce System

A Mini E-commerce REST API built with **Django REST Framework**, plus a
**React** frontend that consumes it.

The API covers categories, products with filtering/searching/ordering/
pagination, token authentication and orders. The frontend is a small shop:
browse and filter a catalog of 49 real products, add things to a cart, log
in, place orders and look at your order history.

It also has a **second side**: organization accounts that run the shop —
working through every customer's orders, managing the catalog and stock,
reading a dashboard, and administering accounts. Customers never see any of
it; see [the organization API](#the-organization-side).

```
┌─────────────────────────┐        HTTP + token auth        ┌──────────────────────────┐
│  React frontend (Vite)  │ ──────────────────────────────▶ │  Django REST Framework   │
│  dev:  localhost:5173   │ ◀────────────────────────────── │  dev:  localhost:8000    │
│  live: Vercel           │           JSON                  │  live: Render            │
└─────────────────────────┘                                 └───────────┬──────────────┘
                                                                        │
                                                            ┌───────────▼──────────────┐
                                                            │  dev:  SQLite            │
                                                            │  live: PostgreSQL (Neon) │
                                                            └──────────────────────────┘
```

## Live demo

| | URL |
| --- | --- |
| **Shop (frontend)** | <https://mini-e-commerce-system-one.vercel.app> |
| **API** | <https://mini-ecommerce-api-alnq.onrender.com/api/> |
| **Admin** | <https://mini-ecommerce-api-alnq.onrender.com/admin/> |

Sign in to the shop with the sample account:

```
username: demo
password: demo12345
```

> **The first request takes about 50 seconds.** The API runs on Render's free
> tier, which spins the service down after ~15 minutes of inactivity. The
> catalog will sit on "Loading products…" while it wakes up; everything is
> immediate after that. Opening the API URL first gets the wake-up out of the
> way.

Things worth trying:

- use the sidebar: search for `laptop`, pick a category, tap a price band,
  tick **In stock only**, then sort by price. Every one of those is done by
  the API, and the query string updates as you go, so any filtered view can
  be shared as a link
- find **Vivo X21** or **Samsung Galaxy S8** — both are out of stock, so
  their cards are greyed out and marked *Sold out*
- add something to the cart and check out — the order appears under
  **My orders**, and the product's stock goes down
- try to order more units than are in stock, and the server refuses with the
  exact quantity available

Hosting: React on Vercel, Django on Render, PostgreSQL on Neon. The admin
account is not published; the setup is described in [DEPLOYMENT.md](DEPLOYMENT.md).

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
python manage.py seed_data --demo-user   # 49 products + demo account
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
python manage.py test               # 246 tests
```

## Sample catalog

`python manage.py seed_data` loads 49 products across 6 categories, each with
a real name, description, price, stock level and photograph:

| Category | Products | Examples |
| --- | --- | --- |
| Smartphones | 16 | iPhone 13 Pro, Samsung Galaxy S10, Vivo X21 |
| Mobile Accessories | 14 | Apple Airpods, Apple MagSafe Battery Pack, Amazon Echo Plus |
| Watches | 6 | Rolex Submariner Watch, Rolex Datejust, Longines Master Collection |
| Laptops | 5 | Apple MacBook Pro 14 Inch Space Grey, Asus Zenbook Pro, Lenovo Yoga 920 |
| Sunglasses | 5 | Classic Sun Glasses, Green and Black Glasses |
| Tablets | 3 | iPad Mini 2021 Starlight, Samsung Galaxy Tab S8 Plus Grey |

Prices run from **$12.99 to $13,999.99**, which makes the price filter and
the price sort visibly do something. **Two products are deliberately out of
stock** (Vivo X21, Samsung Galaxy S8) and three have a single unit left
(Apple Airpower Wireless Charger, Apple MagSafe Battery Pack, Classic Sun
Glasses), so the *Sold out* and *Only 1 left* states, and the
stock-validation error, can all be demonstrated without editing data by
hand.

The data lives in
[`catalog_data.json`](backend/catalog/management/commands/catalog_data.json)
next to the command that loads it, so it can be reviewed, edited or
regenerated without touching any code. Seeding is idempotent — products are
matched by name within their category, so running it twice updates them
rather than creating duplicates.

### Product pictures

A product can get its picture two ways:

| Field | Used for |
| --- | --- |
| `image` | an uploaded file, served from `MEDIA_ROOT` |
| `image_url` | a link to a picture hosted elsewhere |

The API resolves whichever is set into a single `image` field in the
response, so the frontend only ever reads one key. An **uploaded file wins**,
so adding a real photo later replaces the seeded link rather than hiding
behind it, and upload URLs are returned absolute because the frontend runs on
a different origin.

The seeded catalog uses `image_url`. Hosts like Render wipe the filesystem on
every deploy, so uploaded files would disappear and leave the shop
imageless after the first redeploy.

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
| **Optional:** product image | `Product.image` (upload) and `Product.image_url` (hosted elsewhere) |

Beyond the brief: an entire organization side (roles, order lifecycle,
dashboard, customer and account management), 246 automated tests, a seeded
catalog of 49 real products, a React frontend, and deployment
configuration.

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
curl "http://127.0.0.1:8000/api/products/?search=laptop&ordering=price"
curl "http://127.0.0.1:8000/api/products/?category=1&min_price=100&max_price=500"

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo12345"}' | python -c "import json,sys;print(json.load(sys.stdin)['token'])")

curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

## The organization side

Two kinds of account share one login. A **customer** shops; an
**organization user** runs the shop. `Profile.role` — `customer`, `staff` or
`admin` — decides which, and every login reports it, so a client knows which
interface to show without a second request.

| | Customer | Staff | Admin |
| --- | --- | --- | --- |
| Browse the catalog | ✅ | ✅ | ✅ |
| Place and view **their own** orders | ✅ | ✅ | ✅ |
| Change the catalog, adjust stock | — | ✅ | ✅ |
| See and work **every** order | — | ✅ | ✅ |
| Dashboard, customer management | — | ✅ | ✅ |
| Create and manage organization accounts | — | — | ✅ |

```
POST /api/org/orders/{id}/status/      advance an order
POST /api/org/orders/{id}/cancel/      cancel it, returning the stock
GET  /api/org/dashboard/               revenue, counts, best sellers, trend
GET  /api/org/customers/               who buys, what they have spent
POST /api/org/customers/{id}/deactivate/
GET  /api/org/staff/                   colleagues (admin only)
```

Orders move through a lifecycle rather than being edited:

```
pending ──► confirmed ──► processing ──► shipped ──► delivered
   │            │              │
   └────────────┴──────────────┴──► cancelled
```

The rules live on the model, so the API, the admin site and a shell all
behave the same, every transition is recorded with who did it and why, and
cancelling returns the stock exactly once. A shipped order cannot be
cancelled — that needs a returns process.

The first organization admin is created from the command line, because an
API that needs an admin in order to create an admin cannot bootstrap itself:

```bash
python manage.py create_org_user alice --role admin
```

Full endpoint tables are in [backend/README.md](backend/README.md).

## Testing with Postman

Import both files from [`postman/`](postman), select the "Mini E-commerce -
Local" environment, and run **Auth / Login** once — a test script stores the
token, so every protected request then works.

To run the collection against the deployed API instead, change the
environment's `base_url` to
`https://mini-ecommerce-api-alnq.onrender.com/api` — nothing else needs to
change, since no request has a hardcoded host.

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

### The database: Neon

SQLite cannot be used in production — Render's filesystem is ephemeral, so
the file is wiped on every deploy. This project uses
**[Neon](https://neon.com)** (managed PostgreSQL, free tier) via
`DATABASE_URL`.

Render's own free Postgres **expires 30 days after creation**, with no
warning and a 14-day grace period before the data is deleted; Neon's free
tier has no expiry. That matters if a reviewer opens the link weeks after
submission. Nothing in the code depends on the choice, so switching back is
a `render.yaml` edit (documented at the bottom of that file).

Use Neon's **direct** connection string (not the `-pooler` one) and set
`DJANGO_DB_CONN_MAX_AGE=0`, since Neon suspends an idle database.
`python manage.py db_info` reports which database you are actually connected
to, how long it took, and whether TLS is on.

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
- **Uploaded product images do not survive a deploy** (ephemeral disk).
  That is exactly why the seeded catalog references pictures by URL through
  `Product.image_url` instead of uploading them; uploads through the admin
  work locally but are wiped by the next deploy.

## Tech stack

| Backend | Frontend |
| --- | --- |
| Django 5.2 | React 19 |
| Django REST Framework 3.16 | Vite 7 |
| django-filter, django-cors-headers | React Router 7 |
| SQLite (dev) / PostgreSQL (prod) | plain CSS, no UI framework |
| gunicorn + WhiteNoise | — |
