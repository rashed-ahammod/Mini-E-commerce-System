#!/usr/bin/env bash
#
# Render runs this as the Build Command (with `rootDir: backend`, so the
# working directory is backend/).
#
# Render's Free plan gives no shell, so anything that would normally be typed
# after a deploy — migrate, collectstatic, creating an admin user, loading
# sample data — has to happen here.

set -o errexit  # stop at the first failing command

pip install --upgrade pip
pip install -r requirements.txt

# Hashed, compressed static files for the admin and the browsable API.
python manage.py collectstatic --no-input

# Safe to run on every deploy: migrations already applied are skipped.
python manage.py migrate --no-input

# Optional sample catalog. Set SEED_DATA=true in the Render dashboard for the
# first deploy, then set it back to false. The command is idempotent, so a
# second run updates the sample products rather than duplicating them.
if [ "$SEED_DATA" = "true" ]; then
  echo "Loading sample catalog data..."
  python manage.py seed_data --demo-user
fi

# Optional admin account. Django's createsuperuser reads these three
# environment variables when given --no-input. It fails if the user already
# exists, which is expected on later deploys, so that case is ignored.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Ensuring the superuser exists..."
  python manage.py createsuperuser --no-input || echo "Superuser already exists, skipping."
fi
