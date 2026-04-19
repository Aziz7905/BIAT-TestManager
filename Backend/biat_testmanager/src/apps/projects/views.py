#src/app/projects/views.py
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.access import (
    can_create_projects,
    can_manage_project_member_record,
    can_manage_project_record,
    can_view_project_members,
    can_view_projects,
    get_project_queryset_for_actor,
)
from apps.projects.models import ProjectMember
from apps.projects.serializers import (
    ProjectMemberCreateSerializer,
    ProjectMemberSerializer,
    ProjectMemberUpdateSerializer,
    ProjectSerializer,
)
from apps.projects.services import archive_project, remove_project_member, restore_project


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_project_queryset_for_actor(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def list(self, request, *args, **kwargs):
        if not can_view_projects(request.user):
            raise PermissionDenied("You do not have permission to view projects.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_create_projects(request.user):
            raise PermissionDenied("You do not have permission to create projects.")
        return super().create(request, *args, **kwargs)


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_project_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        if not can_view_projects(request.user):
            raise PermissionDenied("You do not have permission to view this project.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        if not can_manage_project_record(request.user, project):
            raise PermissionDenied("You do not have permission to update this project.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if not can_manage_project_record(request.user, project):
            raise PermissionDenied("You do not have permission to delete this project.")
        return super().destroy(request, *args, **kwargs)


class ProjectArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(get_project_queryset_for_actor(request.user), pk=pk)
        if not can_manage_project_record(request.user, project):
            raise PermissionDenied("You do not have permission to archive this project.")

        project = archive_project(project)
        serializer = ProjectSerializer(project, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProjectRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(get_project_queryset_for_actor(request.user), pk=pk)
        if not can_manage_project_record(request.user, project):
            raise PermissionDenied("You do not have permission to restore this project.")

        project = restore_project(project)
        serializer = ProjectSerializer(project, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProjectMemberListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_project(self):
        return get_object_or_404(
            get_project_queryset_for_actor(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get_queryset(self):
        project = self.get_project()
        return ProjectMember.objects.select_related(
            "project",
            "user",
            "user__profile",
        ).filter(project=project).order_by(
            "role",
            "user__first_name",
            "user__last_name",
            "user__email",
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectMemberCreateSerializer
        return ProjectMemberSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def list(self, request, *args, **kwargs):
        project = self.get_project()
        if not can_view_project_members(request.user, project):
            raise PermissionDenied("You do not have permission to view this project's members.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        if not can_manage_project_record(request.user, project):
            raise PermissionDenied("You do not have permission to add members to this project.")
        return super().create(request, *args, **kwargs)


class ProjectMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "membership_pk"

    def get_project(self):
        return get_object_or_404(
            get_project_queryset_for_actor(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get_queryset(self):
        project = self.get_project()
        return ProjectMember.objects.select_related(
            "project",
            "user",
            "user__profile",
        ).filter(project=project)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return ProjectMemberUpdateSerializer
        return ProjectMemberSerializer

    def retrieve(self, request, *args, **kwargs):
        membership = self.get_object()
        if not can_view_project_members(request.user, membership.project):
            raise PermissionDenied("You do not have permission to view this project member.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        if not can_manage_project_member_record(request.user, membership):
            raise PermissionDenied("You do not have permission to update this project member.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if not can_manage_project_member_record(request.user, membership):
            raise PermissionDenied("You do not have permission to remove this project member.")
        remove_project_member(membership)
        return Response(status=204)
