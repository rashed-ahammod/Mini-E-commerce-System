# Deployment — Render (API) + Vercel (frontend)

The two halves deploy separately:

```
   Vercel                         Render
┌──────────────┐   HTTPS +    ┌──────────────────┐       ┌──────────────┐
│  React SPA   │ ───token───▶ │  Django API      │ ────▶ │  PostgreSQL  │
│  static      │              │  gunicorn        │       │              │
└──────────────┘              └──────────────────┘       └──────────────┘
```

Deploy the **backend first** — the frontend needs its URL at build time.

---

## 1. Database: Neon

SQLite cannot be used in production here. Render's filesystem is ephemeral,
so the file would be wiped on every deploy and every restart. The database
has to be PostgreSQL, and this project uses **[Neon](https://neon.com)**.

**Why Neon rather than Render's own free Postgres:** a free Render Postgres
**expires 30 days after it is created**, then gives a 14-day grace period
before the data is deleted. Nothing warns you; a working deployment simply
stops working about a month later. Neon's free tier has no expiry date, which
matters if a reviewer might open your link weeks after you submit it.

Nothing in the application code depends on this choice — `config/settings.py`
reads `DATABASE_URL` and does not care who provides it. Switching back to
Render Postgres later is a change to `render.yaml` only (the bottom of that
file explains how).

### Create the database

1. Sign up at <https://neon.com> (GitHub login works) and create a project.
2. **Pick the region closest to your Render region** — every query crosses
   that distance, and it dominates everything else. Measured from a laptop in
   Asia against a `us-west-2` Neon database: ~250 ms per query and ~2.5 s to
   open a connection. From a Render service in the *same* region those drop
   to single-digit milliseconds. Oregon ↔ `us-west-2`, Frankfurt ↔ EU Central.

   This is also why running the app locally against Neon feels slow: it is
   the distance, not the database. Keep `DATABASE_URL` commented out in
   `backend/.env` for day-to-day development and use SQLite.
3. Name the database something like `mini_ecommerce`.
4. On the project dashboard, open **Connect** and copy the connection
   string. It looks like:

   ```
   postgresql://neondb_owner:npg_XXXX@ep-cool-bird-a1b2c3d4.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### Pooled or direct?

Neon offers two forms of that string. The **direct** one is the default; the
**pooled** one has `-pooler` in the hostname.

| | Direct (recommended here) | Pooled (`-pooler`) |
| --- | --- | --- |
| Use when | A handful of connections — which is this app: Render Free runs 2 gunicorn workers | Many short-lived connections |
| Extra setting | none | `DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS=True` |

The pooler runs in **transaction mode**, handing each transaction a
different backend connection, so anything relying on session state — a
server-side cursor in particular — breaks. Django has a setting for exactly
this, wired to `DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS` in
`config/settings.py`. Two workers do not need pooling, so take the direct
string and skip the complication.

`manage.py db_info` warns you if it sees a `-pooler` host without that flag
set.

### Test it locally before deploying

This is worth doing first: it proves the connection string works and that
the schema builds on PostgreSQL, before Render is involved.

```bash
cd backend

# .env is gitignored, so the credentials stay out of the repository
echo 'DATABASE_URL=postgresql://...your Neon string...' >> .env
echo 'DJANGO_DB_CONN_MAX_AGE=0' >> .env

python manage.py db_info      # which database am I actually on?
python manage.py migrate      # build the schema on Neon
python manage.py seed_data --demo-user
python manage.py createsuperuser
python manage.py runserver
```

`db_info` prints the engine, host, TLS mode and server version, and times the
connection — so a typo in the string or a wrong region shows up immediately
rather than as a failed deploy.

Run the test suite against it too, to be sure nothing in the project depends
on SQLite behaviour:

```bash
python manage.py test
```

The test runner creates and drops a separate `test_neondb` database, so your
real data is untouched.

When you are done testing locally, **remove `DATABASE_URL` from
`backend/.env`** so development goes back to the local SQLite file and you
are not writing to the production database by accident.

### Keep in mind

- **Neon suspends an idle database** and resumes it on the next connection.
  That is why `DJANGO_DB_CONN_MAX_AGE` is `0` in `render.yaml`: a connection
  held open across requests can be dead by the time it is reused. Connecting
  per request costs a few milliseconds.
- **`?sslmode=require` is part of the connection string** — keep it. The app
  also has `DJANGO_DB_SSL_REQUIRE` for providers whose string omits it.
- **The free tier has a storage limit** (around 0.5 GB), which this project
  will not come close to.

## 2. Backend on Render

### Option A — Blueprint (uses [`render.yaml`](render.yaml))

1. Push this repository to GitHub.
2. Render dashboard → **New → Blueprint** → select the repository.
3. Render reads `render.yaml` and creates the web service. It prompts for
   the values marked `sync: false` — paste the **Neon connection string**
   into `DATABASE_URL` there.
4. Leave `CORS_ALLOWED_ORIGINS` empty for now and fill it in after the
   frontend's first deploy (section 3), once the Vercel URL exists.
5. Set `SEED_DATA` to `true` for this first deploy if you want the sample
   catalog, then back to `false` afterwards.

> `SEED_DATA=true` also creates the two accounts the login page publishes —
> `demo` (customer) and `salesman` (organization staff). Without it those
> credentials are printed on the login page but do not exist, and anyone
> trying them gets "Invalid username or password". If you deployed before
> and want them now, set `SEED_DATA=true` for one more deploy: the seed is
> idempotent and updates the sample catalog rather than duplicating it.
>
> If you would rather not publish a staff login at all, remove the
> `SAMPLE_LOGINS` entry in `frontend/src/pages/LoginPage.jsx` — it is the
> only thing that puts those credentials on screen.

### Option B — by hand

Render dashboard → **New → Web Service**, then:

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `./render-build.sh` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --log-file -` |
| Health Check Path | `/healthz/` |

### Environment variables

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | a generated secret — **required**, the app refuses to boot without it |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | the Neon connection string, including `?sslmode=require` |
| `CORS_ALLOWED_ORIGINS` | the Vercel URL, e.g. `https://mini-e-commerce-system-one.vercel.app` |
| `CLOUDINARY_URL` | needed only if you upload pictures — see section 5 |
| `PYTHON_VERSION` | `3.13.5` |
| `SEED_DATA` | `true` for the first deploy, then `false` |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | optional, creates an admin during the build |
| `DJANGO_DB_CONN_MAX_AGE` | `0` — Neon suspends when idle, so connections are not reused across requests |
| `DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS` | `True` only if `DATABASE_URL` is a pooled (`-pooler`) string |
| `CORS_ALLOWED_ORIGIN_REGEXES` | optional, for Vercel preview URLs (see below) |

`DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` do **not** need the
Render URL: `settings.py` reads Render's own `RENDER_EXTERNAL_HOSTNAME` and
adds it to both.

### What the build does

[`backend/render-build.sh`](backend/render-build.sh) installs dependencies,
runs `collectstatic`, applies migrations, and optionally seeds the catalog
and creates an admin user. Render's Free plan gives you no shell, so these
have to happen during the build rather than afterwards.

### Verify

```bash
curl https://<your-service>.onrender.com/healthz/      # {"status": "ok"}
curl https://<your-service>.onrender.com/api/
curl "https://<your-service>.onrender.com/api/products/?search=phone&ordering=price"
```

The admin is at `https://<your-service>.onrender.com/admin/`.

If the catalog comes back empty, the seed did not run: check that `SEED_DATA`
was `true` during the build, and look at the build log for the
"Loading sample catalog data..." line.

---

## 3. Frontend on Vercel

1. Vercel → **Add New → Project** → import the same repository.
2. **Root Directory: `frontend`** — this is the setting people miss, and
   without it the build fails because `package.json` is not at the repo root.
   Framework, build command and output directory come from
   [`frontend/vercel.json`](frontend/vercel.json).
3. Add the environment variable:

   | Name | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://<your-service>.onrender.com/api` |

   No trailing slash. Vite **inlines** this at build time, so changing it
   later requires a redeploy — it is not read at run time.
4. Deploy, then copy the resulting URL into `CORS_ALLOWED_ORIGINS` on Render
   and redeploy the backend (or just save — Render restarts on an env change).

`vercel.json` also rewrites every unmatched path to `index.html`, so
refreshing `/products/3` works instead of returning 404, and caches the
hashed files under `/assets/` permanently.

### Preview deployments

Every Vercel preview gets its own URL, so previews will hit CORS errors
unless you add a regex on Render:

```
CORS_ALLOWED_ORIGIN_REGEXES=^https://mini-ecommerce-[a-z0-9-]+\.vercel\.app$
```

Scope it to your own project name as above. A bare `\.vercel\.app$` pattern
would allow **any** site hosted on Vercel to call your API from a visitor's
browser.

---

## 4. Things that will surprise you on the free tiers

- **The API sleeps.** A free Render service spins down after about 15 minutes
  of inactivity, and the next request takes roughly 50 seconds while it wakes
  up. The frontend shows its loading states during that time, but a reviewer
  opening the link cold will notice. Mention it in your submission, or keep
  the service warm with a scheduled ping.
- **Uploaded images need Cloudinary.** `Product.image` writes through
  Django's storage backend. Without `CLOUDINARY_URL` that is the container's
  own disk, which Render replaces on every deploy — so an uploaded picture
  is gone with the next release while the database row still points at it.
  Set `CLOUDINARY_URL` (section 5) and the bytes go somewhere permanent
  instead. Linked pictures (`image_url`) are unaffected either way.
- **Neon suspends an idle database.** The first query after a quiet period
  pays a small resume cost. This is separate from, and much shorter than,
  Render's own cold start.
- **Vercel previews need the CORS regex**, as above.

---

## 5. Uploaded pictures (Cloudinary)

Only needed if you want to **upload** product photographs. Products that
link to an image (`image_url`) work without any of this, which is what the
seeded catalog does.

### Why it is needed at all

`Product.image` is a `CharField` holding a path — `products/photo.png` — not
the picture. The bytes go wherever Django's storage backend puts them. By
default that is the web container's own disk, and Render builds a brand new
container on every deploy, so:

```
Neon still has     image = 'products/photo.png'   ✅ the row survives
the new container  /media/products/photo.png      ❌ empty disk
result             a row pointing at a file that no longer exists
```

The database is not the problem — it never held the file.

### Setting it up

1. Sign up at <https://cloudinary.com> (the free tier is generous: ~25GB
   storage and transformations).
2. On the dashboard, copy the **API environment variable**. It looks like:

   ```
   cloudinary://123456789012345:abcdefg_hijklmnop@your-cloud-name
   ```

   It carries the cloud name, key and secret together, so it is the only
   value you need — treat it as a password.
3. In Render → your service → **Environment**, add:

   | Variable | Value |
   | --- | --- |
   | `CLOUDINARY_URL` | the URL you copied |

4. Save. Render restarts, and uploads now go to Cloudinary.

Nothing else changes: the model still uses an `ImageField`, the API still
takes the same multipart request, and the console's upload button behaves
identically. Only the storage backend underneath is different.

### Checking it worked

Upload a picture from the console (`/org/products` → Edit → Upload a file)
and look at the product in the API:

```bash
curl https://<your-service>.onrender.com/api/products/<id>/ | grep image
```

The `image` URL should now begin `https://res.cloudinary.com/…` rather than
`https://<your-service>.onrender.com/media/…`. Redeploy and fetch it again —
it should still be there.

### Leaving it unset

Locally, `CLOUDINARY_URL` is unset and uploads go to `backend/media/` as
before. That keeps development offline and the test suite off the network.
Pictures uploaded in development do not appear in production and vice
versa, which is usually what you want.

## 6. After the first successful deploy

1. Set `SEED_DATA` back to `false` so later deploys do not re-run the seed.
2. Remove `DJANGO_SUPERUSER_PASSWORD` from the environment once the admin
   account exists.
3. Confirm the production configuration:

   ```bash
   # locally, with the production variables set
   python manage.py check --deploy
   ```

   The remaining warnings should only be `security.W005` (HSTS subdomains)
   and `security.W021` (HSTS preload), which are deliberate opt-ins — enable
   them with `DJANGO_HSTS_INCLUDE_SUBDOMAINS` once you are sure every
   subdomain is HTTPS-only.
