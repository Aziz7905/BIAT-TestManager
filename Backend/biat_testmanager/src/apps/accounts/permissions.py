from rest_framework.permissions import BasePermission

from accounts.models import UserProfileRole


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.is_staff:
            return True

        profile = getattr(user, "profile", None)
        if not profile:
            return False

        return profile.role in {
            UserProfileRole.PLATFORM_OWNER,
            UserProfileRole.ORG_ADMIN,
        }