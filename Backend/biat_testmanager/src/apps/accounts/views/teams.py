from time import perf_counter

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import AIProvider, TeamMembership
from apps.accounts.serializers import (
    AIProviderSerializer,
    TeamMemberSerializer,
    TeamMembershipCreateSerializer,
    TeamMembershipUpdateSerializer,
    TeamSerializer,
)
from apps.accounts.services.access import (
    can_add_team_members,
    can_create_teams,
    can_manage_team_membership_record,
    can_manage_team_record,
    can_view_teams,
    can_view_team_members,
    get_team_queryset_for_actor,
)
from apps.accounts.services.memberships import delete_team_membership
from apps.ai.providers.base import LLMProviderError, LLMProviderNotConfiguredError
from apps.ai.providers.factory import get_llm_provider


class AIProviderListView(generics.ListAPIView):
    serializer_class = AIProviderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return AIProvider.objects.filter(is_active=True).order_by("name")


class TeamListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_team_queryset_for_actor(self.request.user)

    def list(self, request, *args, **kwargs):
        if not can_view_teams(request.user):
            raise PermissionDenied("You do not have permission to view teams.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_create_teams(request.user):
            raise PermissionDenied("You do not have permission to create teams.")
        return super().create(request, *args, **kwargs)


class TeamDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_team_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        if not can_view_teams(request.user):
            raise PermissionDenied("You do not have permission to view this team.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        team = self.get_object()
        if not can_manage_team_record(request.user, team):
            raise PermissionDenied("You do not have permission to update this team.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        team = self.get_object()
        if not can_manage_team_record(request.user, team):
            raise PermissionDenied("You do not have permission to delete this team.")
        return super().destroy(request, *args, **kwargs)


class TeamAITestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        team = get_object_or_404(get_team_queryset_for_actor(request.user), pk=pk)
        if not can_manage_team_record(request.user, team):
            raise PermissionDenied("You do not have permission to test this team's AI settings.")

        started_at = perf_counter()
        try:
            provider = get_llm_provider(team)
            response = provider.chat(
                [
                    {
                        "role": "system",
                        "content": "You are a health check for BIAT TestManager.",
                    },
                    {
                        "role": "user",
                        "content": "Reply with BIAT_AI_OK only.",
                    },
                ],
                temperature=0,
                max_tokens=16,
            )
        except LLMProviderNotConfiguredError as exc:
            return Response({"ok": False, "error": str(exc)}, status=400)
        except LLMProviderError as exc:
            return Response({"ok": False, "error": str(exc)}, status=502)

        duration_ms = int((perf_counter() - started_at) * 1000)
        return Response(
            {
                "ok": True,
                "provider": provider.name,
                "model": getattr(provider, "model_name", ""),
                "duration_ms": duration_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }
        )


class TeamMemberListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_team(self):
        return get_object_or_404(
            get_team_queryset_for_actor(self.request.user),
            pk=self.kwargs["team_pk"],
        )

    def get_queryset(self):
        team = self.get_team()
        return (
            TeamMembership.objects.select_related(
                "user",
                "user__profile",
            )
            .filter(team=team, is_active=True)
            .order_by("role", "user__first_name", "user__last_name", "user__email")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TeamMembershipCreateSerializer
        return TeamMemberSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["team"] = self.get_team()
        return context

    def list(self, request, *args, **kwargs):
        team = self.get_team()
        if not can_view_team_members(request.user, team):
            raise PermissionDenied("You do not have permission to view this team's members.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        team = self.get_team()
        if not can_add_team_members(request.user, team):
            raise PermissionDenied("You do not have permission to add members to this team.")
        return super().create(request, *args, **kwargs)


class TeamMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "membership_pk"

    def get_team(self):
        return get_object_or_404(
            get_team_queryset_for_actor(self.request.user),
            pk=self.kwargs["team_pk"],
        )

    def get_queryset(self):
        team = self.get_team()
        return TeamMembership.objects.select_related(
            "team",
            "user",
            "user__profile",
        ).filter(team=team)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TeamMembershipUpdateSerializer
        return TeamMemberSerializer

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        if not can_manage_team_membership_record(request.user, membership):
            raise PermissionDenied("You do not have permission to update this team member.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if not can_manage_team_membership_record(request.user, membership):
            raise PermissionDenied("You do not have permission to remove this team member.")
        delete_team_membership(membership)
        return Response(status=204)
