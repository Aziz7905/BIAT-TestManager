from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.api.serializers import (
    AIAuthoringSessionStartSerializer,
    AIGenerationCommitSerializer,
    AIGenerationReviewSerializer,
    AIGenerationSessionSerializer,
    AIGenerationSessionStartSerializer,
)
from apps.ai.models import AIGenerationSession
from apps.ai.providers.base import LLMProviderError
from apps.ai.services.capacity import AICapacityExceededError
from apps.ai.services.sessions import (
    AIGenerationPermissionError,
    apply_review_decisions,
    get_generation_session_queryset_for_actor,
    start_generation_session,
)
from apps.ai.workflows.authoring.service import (
    AIAuthoringError,
    start_browser_authoring_session,
)
from apps.ai.workflows.authoring.trace import save_authoring_trace_as_draft_steps
from apps.ai.workflows.generation.commit import AICommitError, commit_selected_drafts
from apps.automation.models import TestExecution
from apps.automation.serializers import TestExecutionSerializer
from apps.testing.services.access import can_manage_test_design_for_project


class AIGenerationSessionListCreateView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AIGenerationSessionSerializer

    def get_queryset(self):
        queryset = get_generation_session_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def post(self, request):
        serializer = AIGenerationSessionStartSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        try:
            session = start_generation_session(
                user=request.user,
                **serializer.validated_data,
            )
        except AICapacityExceededError as exc:
            raise Throttled(detail=str(exc)) from exc
        except (AIGenerationPermissionError, LLMProviderError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        output = AIGenerationSessionSerializer(session, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class AIGenerationSessionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AIGenerationSessionSerializer

    def get_queryset(self):
        return get_generation_session_queryset_for_actor(self.request.user)


class AIGenerationSessionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        session = get_object_or_404(
            get_generation_session_queryset_for_actor(request.user),
            pk=pk,
        )
        serializer = AIGenerationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = apply_review_decisions(
                session=session,
                decisions=serializer.validated_data["review_decisions"],
                user=request.user,
            )
        except AIGenerationPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(AIGenerationSessionSerializer(session).data)


class AIGenerationSessionCommitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(
            get_generation_session_queryset_for_actor(request.user),
            pk=pk,
        )
        if not can_manage_test_design_for_project(request.user, session.project):
            raise PermissionDenied(
                "You do not have permission to save generated tests for this project."
            )

        serializer = AIGenerationCommitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            summary = commit_selected_drafts(
                session=session,
                create_as_approved=serializer.validated_data["create_as_approved"],
            )
        except AICommitError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        refreshed = AIGenerationSession.objects.get(pk=session.pk)
        return Response(
            {
                "session": AIGenerationSessionSerializer(refreshed).data,
                "created": summary,
            },
            status=status.HTTP_201_CREATED,
        )


class AIAuthoringSessionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIAuthoringSessionStartSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        try:
            execution = start_browser_authoring_session(
                user=request.user,
                **serializer.validated_data,
            )
        except AIAuthoringError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        except LLMProviderError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(
            TestExecutionSerializer(execution, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AIAuthoringTraceSaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, execution_pk):
        execution = get_object_or_404(
            TestExecution.objects.select_related(
                "test_case",
                "test_case__scenario",
                "test_case__scenario__section",
                "test_case__scenario__section__suite",
                "test_case__scenario__section__suite__project",
            ),
            pk=execution_pk,
        )
        try:
            summary = save_authoring_trace_as_draft_steps(
                execution=execution,
                user=request.user,
            )
        except AIAuthoringError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(summary, status=status.HTTP_200_OK)
