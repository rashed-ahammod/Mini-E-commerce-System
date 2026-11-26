"""Report which database the project is actually connected to.

    python manage.py db_info

Useful when setting up a hosted database: it answers "am I talking to Neon
or still to the local SQLite file?" in one command, and shows whether the
connection is encrypted and how slow it is.

(This is a project-wide utility rather than a catalog one; it lives here
because `catalog` already has the management command package.)
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Show the database this project is connected to."

    def handle(self, *args, **options):
        config = settings.DATABASES["default"]
        engine = config["ENGINE"].rsplit(".", 1)[-1]

        self.stdout.write(self.style.MIGRATE_HEADING("Configured"))
        self.stdout.write(f"  engine         : {engine}")
        self.stdout.write(f"  name           : {config['NAME']}")

        if engine == "sqlite3":
            self.stdout.write(
                self.style.WARNING(
                    "\n  Using the local SQLite file. DATABASE_URL is not set.\n"
                    "  That is correct for development, but it cannot be used in\n"
                    "  production: hosts like Render wipe the filesystem on deploy."
                )
            )
        else:
            self.stdout.write(f"  host           : {config['HOST']}")
            self.stdout.write(f"  port           : {config['PORT'] or 'default'}")
            self.stdout.write(f"  user           : {config['USER']}")
            self.stdout.write(f"  sslmode        : {config.get('OPTIONS', {}).get('sslmode', 'not set')}")

        self.stdout.write(f"  conn_max_age   : {config['CONN_MAX_AGE']}s")
        self.stdout.write(f"  health checks  : {config.get('CONN_HEALTH_CHECKS')}")
        self.stdout.write(
            f"  server-side cursors disabled: "
            f"{config.get('DISABLE_SERVER_SIDE_CURSORS', False)}"
        )

        # Pooled connection strings route through a pooler in transaction
        # mode, which needs DISABLE_SERVER_SIDE_CURSORS to be on.
        host = str(config.get("HOST") or "")
        pooled = "-pooler" in host or str(config.get("PORT")) == "6543"
        if pooled and not config.get("DISABLE_SERVER_SIDE_CURSORS", False):
            self.stdout.write(
                self.style.WARNING(
                    "\n  This looks like a pooled connection string, but server-side\n"
                    "  cursors are still enabled. Set\n"
                    "  DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS=True, or use the direct\n"
                    "  (non-pooled) connection string instead."
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\nConnecting"))
        started = time.perf_counter()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                elapsed = (time.perf_counter() - started) * 1000
                version = connection.Database.__name__
                if engine != "sqlite3":
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()[0]
        except Exception as error:  # noqa: BLE001 - we want to report anything
            self.stdout.write(self.style.ERROR(f"  failed: {error}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"  connected in {elapsed:.0f} ms"))
        self.stdout.write(f"  server         : {str(version)[:80]}")

        applied = len(connection.introspection.table_names())
        self.stdout.write(f"  tables present : {applied}")
        if applied == 0:
            self.stdout.write(
                self.style.WARNING("  No tables yet - run `python manage.py migrate`.")
            )
