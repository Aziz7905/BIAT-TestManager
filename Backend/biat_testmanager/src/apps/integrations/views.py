from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Team
from apps.integrations.access import (
    can_manage_project_integrations,
    can_manage_team_integrations,
    can_view_project_integrations,
)
from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationConfig,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)
from apps.integrations.serializers import (
    ExternalIssueLinkSerializer,
    IntegrationActionLogSerializer,
    IntegrationConfigSerializer,
    IntegrationConfigWriteSerializer,
    RepositoryBindingSerializer,
    UserIntegrationCredentialSerializer,
    UserIntegrationCredentialWriteSerializer,
    WebhookEventDetailSerializer,
    WebhookEventListSerializer,
)
from apps.integrations.services import process_webhook_event, verify_webhook_signature
from apps.projects.access import get_project_queryset_for_actor


class TeamIntegrationConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get_team(self):
        return get_object_or_404(
            Team.objects.select_related("organization"),
            pk=self.kwargs["team_pk"],
        )

    def get(self, request, team_pk, provider_slug):
        team = self.get_team()
        if not can_manage_team_integrations(request.user, team):
            raise PermissionDenied("You do not have permission to view this team integration.")
        config = get_object_or_404(
            IntegrationConfig.objects.select_related("team", "project"),
            team=team,
            project=None,
            provider_slug=provider_slug,
        )
        return Response(IntegrationConfigSerializer(config).data)

    def put(self, request, team_pk, provider_slug):
        team = self.get_team()
        serializer = IntegrationConfigWriteSerializer(
            data=request.data,
            context={
                "request": request,
                "team": team,
                "provider_slug": provider_slug,
            },
        )
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(IntegrationConfigSerializer(config).data)


class ProjectIntegrationConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self):
        return get_object_or_404(
            get_project_queryset_for_actor(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get(self, request, project_pk, provider_slug):
        project = self.get_project()
        if not can_manage_project_integrations(request.user, project):
            raise PermissionDenied("You do not have permission to view this project integration.")
        config = get_object_or_404(
            IntegrationConfig.objects.select_related("team", "project"),
            project=project,
            provider_slug=provider_slug,
        )
        return Response(IntegrationConfigSerializer(config).data)

    def put(self, request, project_pk, provider_slug):
        project = self.get_project()
        serializer = IntegrationConfigWriteSerializer(
            data=request.data,
            context={
                "request": request,
                "project": project,
                "provider_slug": provider_slug,
            },
        )
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(IntegrationConfigSerializer(config).data)


class MyIntegrationCredentialView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, provider_slug):
        credential = get_object_or_404(
            UserIntegrationCredential.objects.select_related(
                "user_profile",
                "user_profile__user",
            ),
            user_profile=request.user.profile,
            provider_slug=provider_slug,
        )
        return Response(UserIntegrationCredentialSerializer(credential).data)

    def put(self, request, provider_slug):
        serializer = UserIntegrationCredentialWriteSerializer(
            data=request.data,
            context={"request": request, "provider_slug": provider_slug},
        )
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        return Response(UserIntegrationCredentialSerializer(credential).data)


class RepositoryBindingListCreateView(generics.ListCreateAPIView):
    serializer_class = RepositoryBindingSerializer
    permission_classes = [IsAuthenticated]

    def get_project(self):
        return get_object_or_404(
            get_project_queryset_for_actor(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get_queryset(self):
        project = self.get_project()
        if not can_view_project_integrations(self.request.user, project):
            raise PermissionDenied("You do not have permission to view repository bindings.")
        return RepositoryBinding.objects.select_related(
            "project",
            "created_by",
        ).filter(project=project).order_by("provider_slug", "repo_identifier")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        if not can_manage_project_integrations(request.user, project):
            raise PermissionDenied("You do not have permission to create repository bindings.")
        return super().create(request, *args, **kwargs)


class RepositoryBindingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RepositoryBindingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_qs = get_project_queryset_for_actor(self.request.user)
        return RepositoryBinding.objects.select_related(
            "project",
            "created_by",
        ).filter(project__in=project_qs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_object().project
        return context

    def destroy(self, request, *args, **kwargs):
        binding = self.get_object()
        if not can_manage_project_integrations(request.user, binding.project):
            raise PermissionDenied("You do not have permission to delete this repository binding.")
        binding.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, provider_slug):
        raw_body = request.body
        payload_json = request.data if isinstance(request.data, dict) else {}
        binding = verify_webhook_signature(
            provider_slug=provider_slug,
            payload_json=payload_json,
            raw_body=raw_body,
            headers=request.headers,
        )
        event_type = (
            request.headers.get("X-GitHub-Event")
            or request.headers.get("X-Jenkins-Event")
            or payload_json.get("event_type")
            or "unknown"
        )
        external_id = (
            request.headers.get("X-GitHub-Delivery")
            or request.headers.get("X-Request-Id")
            or payload_json.get("external_id")
        )
        headers_json = {
            key: value
            for key, value in request.headers.items()
            if key.lower().startswith("x-")
        }
        headers_json["signature_verified"] = True
        event, created = process_webhook_event(
            provider_slug=provider_slug,
            event_type=event_type,
            external_id=external_id,
            payload_json=payload_json,
            headers_json=headers_json,
            repository_binding=binding,
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(WebhookEventListSerializer(event).data, status=response_status)


class WebhookEventListView(generics.ListAPIView):
    serializer_class = WebhookEventListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_qs = get_project_queryset_for_actor(self.request.user)
        queryset = WebhookEvent.objects.select_related(
            "project",
            "repository_binding",
        ).filter(project__in=project_qs)
        provider_slug = self.request.query_params.get("provider")
        if provider_slug:
            queryset = queryset.filter(provider_slug=provider_slug)
        return queryset.order_by("-received_at")


class WebhookEventDetailView(generics.RetrieveAPIView):
    serializer_class = WebhookEventDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_qs = get_project_queryset_for_actor(self.request.user)
        return WebhookEvent.objects.select_related(
            "project",
            "repository_binding",
        ).filter(project__in=project_qs)


class ExternalIssueLinkListCreateView(generics.ListCreateAPIView):
    serializer_class = ExternalIssueLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_project(self):
        return get_object_or_404(
            get_project_queryset_for_actor(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def get_queryset(self):
        project = self.get_project()
        if not can_view_project_integrations(self.request.user, project):
            raise PermissionDenied("You do not have permission to view external issue links.")
        return ExternalIssueLink.objects.select_related(
            "project",
            "content_type",
            "created_by",
        ).filter(project=project)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        if not can_manage_project_integrations(request.user, project):
            raise PermissionDenied("You do not have permission to create external issue links.")
        return super().create(request, *args, **kwargs)


class IntegrationActionLogListView(generics.ListAPIView):
    serializer_class = IntegrationActionLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_qs = get_project_queryset_for_actor(self.request.user)
        queryset = IntegrationActionLog.objects.select_related(
            "team",
            "project",
            "actor_user",
        ).filter(project__in=project_qs)
        provider_slug = self.request.query_params.get("provider")
        if provider_slug:
            queryset = queryset.filter(provider_slug=provider_slug)
        return queryset.order_by("-created_at")
