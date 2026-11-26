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
# environment variables when given --no-input, and ALL THREE are required:
# with the email missing it exits with "You must use --email with --noinput",
# which would otherwise be mistaken for "the user already exists" and leave
# you without an admin account.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] || [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  if [ -z "$DJANGO_SUPERUSER_USERNAME" ] || [ -z "$DJANGO_SUPERUSER_EMAIL" ] || [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "WARNING: skipping superuser creation."
    echo "         Set all three of DJANGO_SUPERUSER_USERNAME,"
    echo "         DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD."
  else
    echo "Ensuring the superuser exists..."
    # Fails when the account is already there, which is normal on every
    # deploy after the first, so that case is reported and ignored.
    python manage.py createsuperuser --no-input \
      || echo "Superuser '$DJANGO_SUPERUSER_USERNAME' already exists; leaving it as it is."
  fi
fi
