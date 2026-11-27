"""Show the role alongside each user in the Django admin.

The profile is edited inline on the user page rather than as a separate
model, because a profile without its user is meaningless.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "profile"
    fields = ("role", "phone", "address", "department")


class UserAdmin(DjangoUserAdmin):
    inlines = [ProfileInline]
    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = DjangoUserAdmin.list_filter + ("profile__role",)

    @admin.display(description="role", ordering="profile__role")
    def role(self, user: User) -> str:
        profile = getattr(user, "profile", None)
        return profile.get_role_display() if profile else "—"

    def get_queryset(self, request):
        # One query for the list instead of one per row.
        return super().get_queryset(request).select_related("profile")


# Replace Django's registration with the one that shows roles.
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
