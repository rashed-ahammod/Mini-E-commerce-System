"""Permission classes for the two kinds of account.

Having these as named classes keeps the rule in one place: a view says
`permission_classes = [IsOrganizationUser]` and the meaning of that cannot
drift between views.
"""

from rest_framework import permissions

from .models import profile_for


class IsOrganizationUser(permissions.BasePermission):
    """Only organization staff and admins (and superusers)."""

    message = "This endpoint is for organization users."

    def has_permission(self, request, view):
        profile = profile_for(request.user)
        return bool(profile and profile.is_organization)


class IsOrganizationAdmin(permissions.BasePermission):
    """Only organization admins — managing other organization accounts."""

    message = "This action requires an organization admin account."

    def has_permission(self, request, view):
        profile = profile_for(request.user)
        return bool(profile and profile.is_organization_admin)


class IsOrganizationUserOrReadOnly(permissions.BasePermission):
    """Anyone may read; only organization users may change anything.

    Used for the catalog: the shop front has to be public, but a customer
    must not be able to edit products or invent categories.
    """

    message = "Only organization users can change the catalog."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        profile = profile_for(request.user)
        return bool(profile and profile.is_organization)
