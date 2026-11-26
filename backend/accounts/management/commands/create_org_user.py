"""Create an organization account from the command line.

    python manage.py create_org_user alice --role admin
    python manage.py create_org_user bob --role staff --email bob@shop.com
    python manage.py create_org_user alice --role admin --promote

This is how the *first* organization admin comes into existence: the API
refuses to create organization accounts unless an organization admin is
already signed in, which would otherwise be a chicken-and-egg problem. After
that, accounts can be created through the API.

The password is asked for interactively so it never lands in your shell
history; pass --password only in a script you trust.
"""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, profile_for

User = get_user_model()


class Command(BaseCommand):
    help = "Create (or promote) an organization staff or admin account."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--role",
            choices=[Role.STAFF.value, Role.ADMIN.value],
            default=Role.STAFF.value,
            help="staff runs day-to-day operations; admin can also manage "
            "other organization accounts.",
        )
        parser.add_argument("--email", default="")
        parser.add_argument("--department", default="")
        parser.add_argument(
            "--password",
            help="Skip the interactive prompt. Avoid in a shared shell.",
        )
        parser.add_argument(
            "--promote",
            action="store_true",
            help="Allow changing the role of an existing user instead of "
            "failing because the username is taken.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        role = options["role"]
        existing = User.objects.filter(username__iexact=username).first()

        if existing and not options["promote"]:
            raise CommandError(
                f"User '{username}' already exists. "
                f"Re-run with --promote to change their role to {role}."
            )

        if existing:
            profile = profile_for(existing)
            previous = profile.role
            profile.role = role
            if options["department"]:
                profile.department = options["department"]
            profile.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Promoted '{username}' from {previous} to {role}."
                )
            )
            return

        password = options["password"] or getpass("Password: ")
        if not password:
            raise CommandError("A password is required.")

        try:
            validate_password(password)
        except ValidationError as error:
            # Report every rule that failed, the way the API would.
            raise CommandError("\n".join(error.messages)) from error

        user = User.objects.create_user(
            username=username,
            email=options["email"],
            password=password,
        )
        profile = profile_for(user)
        profile.role = role
        profile.department = options["department"]
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(f"Created organization {role}: {username}")
        )
        self.stdout.write(
            "They can now log in at /api/auth/login/ like any other user; "
            "the response will say role=" + role + "."
        )
