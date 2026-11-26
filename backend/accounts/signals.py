"""Keep a Profile alongside every User.

Registering this as a signal rather than overriding `create_user` means the
profile also appears for users made in the Django admin, by `createsuperuser`
or by a test factory — anywhere a User is saved.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
