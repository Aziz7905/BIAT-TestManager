from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import Organization
from apps.accounts.serializers import OrganizationSerializer
from apps.accounts.services.access import can_manage_organizations


class OrganizationListCreateView(generics.ListCreateAPIView):
    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        if not can_manage_organizations(request.user):
            raise PermissionDenied("Only the platform owner can view organizations.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_manage_organizations(request.user):
            raise PermissionDenied("Only the platform owner can create organizations.")
        return super().create(request, *args, **kwargs)


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        if not can_manage_organizations(request.user):
            raise PermissionDenied("Only the platform owner can view organizations.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not can_manage_organizations(request.user):
            raise PermissionDenied("Only the platform owner can update organizations.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not can_manage_organizations(request.user):
            raise PermissionDenied("Only the platform owner can delete organizations.")
        return super().destroy(request, *args, **kwargs)