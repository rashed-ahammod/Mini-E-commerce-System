# Backend — Mini E-commerce REST API

Django 5 + Django REST Framework API covering categories, products
(with filtering, search, ordering and pagination), token authentication
and orders.

**Deployed:** <https://mini-ecommerce-api-alnq.onrender.com/api/> (Render,
with PostgreSQL on Neon). The first request after a quiet period takes about
50 seconds while the free instance wakes up.

## Project layout

```
backend/
├── config/                 project settings, root URLs, shared pagination
│   ├── settings.py         everything environment-driven
│   ├── pagination.py       DefaultPagination (10 per page, ?page_size up to 100)
│   ├── urls.py             mounts every app under /api/
│   └── views.py            GET /api/ endpoint index
├── accounts/               register / login / logout / me
├── catalog/                Category and Product
│   ├── models.py
│   ├── serializers.py
│   ├── filters.py          ProductFilter (category, price range, in_stock)
│   ├── views.py            CategoryViewSet, ProductViewSet
│   ├── management/commands/seed_data.py
│   └── management/commands/catalog_data.json   the sample catalog
├── orders/                 Order model, serializer with stock validation, viewset
├── manage.py
├── requirements.txt
└── .env.example            copy to .env
```

## Running it

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate elsewhere)
pip install -r requirements.txt
copy .env.example .env            # cp on macOS/Linux
python manage.py migrate
python manage.py seed_data --demo-user   # 49 products + demo/demo12345
python manage.py createsuperuser         # optional, for /admin/
python manage.py runserver
```

- API: <http://127.0.0.1:8000/api/>
- Admin: <http://127.0.0.1:8000/admin/>

`seed_data` loads **49 products across 6 categories** (Smartphones, Mobile
Accessories, Watches, Laptops, Sunglasses, Tablets), each with a real name,
description, price, stock level and photograph. Two are deliberately out of
stock and three have a single unit left, so the sold-out state and the
stock-validation error can be demonstrated without editing data.

The catalog itself lives in
[`catalog/management/commands/catalog_data.json`](catalog/management/commands/catalog_data.json),
separate from the command that loads it, so the data can be reviewed or
regenerated without touching code.

It is safe to run repeatedly — products are matched by name within their
category, so a second run updates them instead of creating duplicates. Add
`--flush` to wipe the catalog (and orders) first.

## Management commands

| Command | What it does |
| --- | --- |
| `python manage.py seed_data` | Load the 49-product sample catalog. `--flush` clears first, `--demo-user` adds a `demo` account |
| `python manage.py db_info` | Report which database is actually in use: engine, host, TLS mode, server version, connection time and table count |

`db_info` is the quickest way to tell whether you are on the local SQLite
file or a hosted PostgreSQL, and it warns if a pooled connection string is
used without `DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS`. See
[../DEPLOYMENT.md](../DEPLOYMENT.md) for the database setup.

## Authentication

Token authentication. Log in once, then send the token on every protected
request:

```
Authorization: Token 9f2c1b7e0a4d...
```

Reading the catalog is public. Creating, updating or deleting anything, and
everything under `/api/orders/`, requires a token.

## Endpoints

### Auth — `/api/auth/`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/register/` | — | Create an account. Returns `{token, user}` (201) so the client is logged in straight away. |
| POST | `/login/` | — | `{username, password}` → `{token, user}`. |
| POST | `/logout/` | token | Deletes the token (204). The old token then returns 401. |
| GET | `/me/` | token | The user the token belongs to. |

### Categories — `/api/categories/`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | — | List, paginated, each with `product_count`. |
| POST | `/` | token | Create. |
| GET | `/{id}/` | — | Single category. |
| PUT / PATCH | `/{id}/` | token | Full / partial update. |
| DELETE | `/{id}/` | token | Delete (204), or **409** if one of its products belongs to an order. |

Supports `?search=` (name, description) and `?ordering=name|created_at`.

### Products — `/api/products/`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | — | List, paginated. |
| POST | `/` | token | Create. |
| GET | `/{id}/` | — | Product details. |
| PUT / PATCH | `/{id}/` | token | Full / partial update. |
| DELETE | `/{id}/` | token | Delete (204), or **409** if the product belongs to an order. |

Query parameters, all combinable:

| Parameter | Example | Effect |
| --- | --- | --- |
| `search` | `?search=phone` | Case-insensitive match on name and description |
| `category` | `?category=1` | Category id |
| `category_name` | `?category_name=phones` | Category name |
| `price` | `?price=149.50` | Exact price |
| `min_price` / `max_price` | `?min_price=100&max_price=500` | Price range |
| `in_stock` | `?in_stock=true` | Only products with stock left |
| `ordering` | `?ordering=price`, `?ordering=-price` | `price`, `name`, `created_at`, `stock` |
| `page` / `page_size` | `?page=2&page_size=20` | Pagination (page_size capped at 100) |

A product reads back with its category nested, but is **written** with a plain
id:

```jsonc
// GET /api/products/1/
{
  "id": 1, "name": "iPhone 13 Pro", "price": "1099.00", "stock": 32,
  "in_stock": true,
  "category": { "id": 1, "name": "Smartphones" },
  "image": "https://cdn.example.com/iphone-13-pro.webp",
  "created_at": "...", "updated_at": "..."
}

// POST /api/products/
{ "name": "iPhone 13 Pro", "price": "1099.00", "stock": 32, "category_id": 1 }
```

#### Product pictures

A product can get a picture from either of two model fields:

| Field | Used for |
| --- | --- |
| `image` | an uploaded file, served from `MEDIA_ROOT` |
| `image_url` | a link to a picture hosted elsewhere |

Responses collapse both into a single read-only **`image`** key, so a client
never has to decide which one to read. Writes use `image_upload` (a file) or
`image_url` (a link):

```jsonc
// PATCH /api/products/1/   — point at a hosted picture
{ "image_url": "https://cdn.example.com/iphone-13-pro.webp" }
```

An uploaded file takes precedence over `image_url`, so adding a real photo
later replaces the seeded link rather than hiding behind it, and upload URLs
are returned absolute because the frontend runs on a different origin.

The seeded catalog uses `image_url`: hosts such as Render wipe the filesystem
on every deploy, so uploaded files would vanish and leave the shop
imageless.

### Orders — `/api/orders/`

All endpoints require a token, and only ever touch the caller's own orders.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/` | Place an order: `{"product_id": 1, "quantity": 2}` |
| GET | `/` | The caller's orders, newest first, paginated |
| GET | `/{id}/` | One of the caller's orders |

The request body carries only `product_id` and `quantity`. The user comes from
the token and `unit_price` / `total_price` are calculated on the server, so a
client cannot choose what it pays or order on someone else's behalf. Orders
cannot be edited or deleted through the API (405) — an order is a record of
something that happened.

Ordering more than the available stock returns 400 and leaves stock untouched:

```json
{ "quantity": ["Only 3 unit(s) of 'iPhone 13 Pro' are in stock."] }
```

A successful order reduces the product's stock by the ordered quantity.

### Status codes used

| Code | When |
| --- | --- |
| 200 / 201 / 204 | Success / created / deleted |
| 400 | Validation failed — the body names the offending field |
| 401 | Missing, malformed or invalidated token |
| 404 | No such object — including another user's order |
| 405 | Method not allowed (e.g. editing an order) |
| 409 | Delete refused because existing orders reference the object |

## Automated tests

```bash
python manage.py test              # whole suite
python manage.py test orders       # one app
python manage.py test orders.tests.CreateOrderTests.test_successful_order_reduces_stock
```

70 tests run against a throwaway database, so they never touch `db.sqlite3`.

| File | Covers |
| --- | --- |
| `accounts/tests.py` | registration (hashing, weak and duplicate usernames), login, the identical message for wrong password vs unknown user, `me`, token invalidation on logout |
| `catalog/tests.py` | category and product CRUD, read-public / write-authenticated, every filter, search, ordering and pagination parameter, the 409 on deleting something an order references, and how a product's picture is resolved |
| `orders/tests.py` | server-calculated prices, stock decrement, every stock-validation path, the price snapshot, order isolation between users, and 405 on editing an order |

The ones worth reading first are the behaviours that are easy to get wrong:
`test_client_cannot_choose_its_own_price`, `test_a_rejected_order_leaves_stock_untouched`,
`test_stock_cannot_be_oversold_by_repeated_orders` and
`test_another_users_order_returns_404_not_403`.

## Testing with Postman

[`postman/`](../postman) in the repository root holds a collection and an
environment. Import both, select the "Mini E-commerce - Local" environment,
and run `Auth / Login` once — a test script stores the token, so every
protected request then works.

No request has a hardcoded id: test scripts save `category_id`, `product_id`,
`new_category_id`, `new_product_id` and `order_id` into the environment, and
the delete requests only touch objects the collection itself created. The
whole collection can therefore be run top to bottom with the Collection
Runner. `Auth / Logout` is deliberately last, because it invalidates the
token.

## Design notes

Things that were a deliberate choice rather than the obvious default:

- **`Order.unit_price`** snapshots the product price at order time, so editing
  a product's price later never rewrites past orders. `total_price` is derived
  from it in `Order.save()`.
- **`Order.product` uses `on_delete=PROTECT`**, so order history cannot be
  erased by deleting a product. `ProtectedDeleteMixin` in
  `catalog/views.py` turns the resulting database error into a 409 with a
  readable message instead of a 500.
- **Stock is validated twice**: `OrderSerializer.validate()` produces the
  friendly error message, and `create()` checks again inside
  `transaction.atomic()` after re-reading the row, because another order could
  land between the two. Note that `select_for_update()` is a no-op on SQLite
  (which serialises writes database-wide anyway); it becomes a real row lock
  when `DATABASE_URL` points at PostgreSQL.
- **Order querysets are filtered by `request.user`**, so another user's order
  returns 404 rather than 403 — that way order ids are not leaked either.
- **Login failures return one message** for both a wrong password and an
  unknown username, so the endpoint cannot be used to discover accounts.
- **Pictures are referenced by URL, not uploaded**, in the seeded catalog.
  `Product.image` (upload) still exists and wins when set, but a deploy on an
  ephemeral filesystem would delete uploaded files, so the sample data uses
  `Product.image_url` and the serializer resolves whichever is present.

## Configuration

Every environment variable is documented in [.env.example](.env.example).
Nothing secret is hardcoded in `config/settings.py`; the fallbacks there are
development-only, and `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False` and
`DJANGO_ALLOWED_HOSTS` must be set before deploying.
