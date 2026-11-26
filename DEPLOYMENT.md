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

## 1. Choose where the database lives

SQLite cannot be used in production here: Render's filesystem is ephemeral,
so the file would be wiped on every deploy and on every restart. It has to be
PostgreSQL. Two realistic options:

| | **Render Postgres (Free)** | **Neon / Supabase (Free)** |
| --- | --- | --- |
| Setup | Created automatically by `render.yaml` | Sign up, copy a connection string |
| Lifetime | **Expires 30 days after creation**, then a 14-day grace period before the data is deleted | No expiry |
| Storage | 1 GB, one free database per workspace | ~0.5 GB (Neon free) |
| Latency to Render | Same platform, very low | Slightly higher, pick the nearest region |
| Best for | Trying it out, short-lived demos | **Anything that must keep working**, e.g. a submitted assignment or a portfolio link |

**Recommendation:** if a reviewer might open this more than a month from now,
use **Neon**. The 30-day expiry is the one thing most likely to make a
working deployment appear broken later, and it is invisible until it
happens.

Either way the application code is identical — `config/settings.py` reads
`DATABASE_URL` and does not care who provides it.

### Using Neon (or another external Postgres)

1. Create a project at <https://neon.com>, copy the connection string
   (`postgres://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`).
2. In `render.yaml`, delete the whole `databases:` block at the bottom and
   change the `DATABASE_URL` entry to:

   ```yaml
   - key: DATABASE_URL
     sync: false
   ```

3. Paste the connection string into Render when it asks for that value.
4. Set `DJANGO_DB_CONN_MAX_AGE=0`, because Neon suspends an idle database and
   a connection held open across requests can go stale.

---

## 2. Backend on Render

### Option A — Blueprint (uses [`render.yaml`](render.yaml))

1. Push this repository to GitHub.
2. Render dashboard → **New → Blueprint** → select the repository.
3. Render reads `render.yaml` and creates the web service (and the database,
   unless you removed that block). It will prompt for the values marked
   `sync: false`.
4. Set `CORS_ALLOWED_ORIGINS` after step 3 of the frontend, once the Vercel
   URL exists. Leave it empty for the first deploy.

### Option B — by hand

Render dashboard → **New → Web Service**, then:

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `./render-build.sh` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --log-file -` |
| Health Check Path | `/api/` |

### Environment variables

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | a generated secret — **required**, the app refuses to boot without it |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | from Render Postgres, or your Neon/Supabase string |
| `CORS_ALLOWED_ORIGINS` | the Vercel URL, e.g. `https://mini-ecommerce.vercel.app` |
| `PYTHON_VERSION` | `3.13.5` |
| `SEED_DATA` | `true` for the first deploy, then `false` |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | optional, creates an admin during the build |
| `DJANGO_DB_CONN_MAX_AGE` | `0` if using Neon or another database that suspends when idle |
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
curl https://<your-service>.onrender.com/api/
curl "https://<your-service>.onrender.com/api/products/?search=phone&ordering=price"
```

The admin is at `https://<your-service>.onrender.com/admin/`.

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
- **Uploaded images do not survive a deploy.** `Product.image` writes to the
  local filesystem, which Render wipes on each deploy. The seeded catalog has
  no images, so this only matters if you upload some. Fixing it properly
  means object storage (Cloudinary, S3) — out of scope here, but worth
  knowing before you demo an upload.
- **A free Render Postgres expires after 30 days.** See section 1.
- **Vercel previews need the CORS regex**, as above.

---

## 5. After the first successful deploy

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
