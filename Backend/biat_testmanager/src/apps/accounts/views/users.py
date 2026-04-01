from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import UserProfileRole
from apps.accounts.serializers import (
    AdminCreateUserSerializer,
    AdminUpdateUserSerializer,
    AdminUserSerializer,
)
from apps.accounts.services.access import (
    can_create_users,
    can_delete_users,
    can_manage_target_user,
    can_update_users,
    can_view_users,
    get_user_queryset_for_actor,
)


class AdminUserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_user_queryset_for_actor(self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminCreateUserSerializer
        return AdminUserSerializer

    def list(self, request, *args, **kwargs):
        if not can_view_users(request.user):
            raise PermissionDenied("You do not have permission to view users.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_create_users(request.user):
            raise PermissionDenied("You do not have permission to create users.")
        return super().create(request, *args, **kwargs)


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_user_queryset_for_actor(self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return AdminUpdateUserSerializer
        return AdminUserSerializer

    def update(self, request, *args, **kwargs):
        if not can_update_users(request.user):
            raise PermissionDenied("You do not have permission to update users.")
        target = self.get_object()
        if not can_manage_target_user(request.user, target):
            raise PermissionDenied("You do not have permission to update this user.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not can_delete_users(request.user):
            raise PermissionDenied("You do not have permission to delete users.")

        target = self.get_object()
        if not can_manage_target_user(request.user, target):
            raise PermissionDenied("You do not have permission to delete this user.")
        target_profile = getattr(target, "profile", None)

        if target_profile and target_profile.role == UserProfileRole.PLATFORM_OWNER:
            raise PermissionDenied("You cannot delete the platform owner.")

        return super().destroy(request, *args, **kwargs)
