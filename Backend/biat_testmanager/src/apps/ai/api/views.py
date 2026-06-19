from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, Throttled, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.api.serializers import (
    AIAuthoringSessionStartSerializer,
    AIGenerationClarifySerializer,
    AIGenerationCommitSerializer,
    AIGenerationRefineSerializer,
    AIGenerationReviewSerializer,
    AIGenerationSessionSerializer,
    AIGenerationSessionStartSerializer,
)
from apps.ai.models import AIGenerationSession
from apps.ai.providers.base import LLMProviderError
from apps.ai.services.capacity import AICapacityExceededError
from apps.ai.services.sessions import (
    AIGenerationPermissionError,
    answer_clarification,
    apply_review_decisions,
    cancel_generation_session,
    get_generation_session_queryset_for_actor,
    request_draft_refinement,
    start_generation_session,
)
from apps.ai.workflows.authoring.commit_script import (
    commit_authoring_trace_as_selenium_script,
)
from apps.ai.workflows.authoring.service import (
    AIAuthoringError,
    start_browser_authoring_session,
)
from apps.ai.workflows.authoring.trace import save_authoring_trace_as_draft_steps
from apps.ai.workflows.generation.commit import AICommitError, commit_selected_drafts
from apps.automation.models import TestExecution
from apps.automation.serializers import AutomationScriptSerializer, TestExecutionSerializer
from apps.testing.services.access import can_manage_test_design_for_project


class AIGenerationSessionListCreateView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AIGenerationSessionSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = get_generation_session_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def post(self, request):
        request_data = _normalize_generation_start_data(request)
        serializer = AIGenerationSessionStartSerializer(
            data=request_data,
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


def _normalize_generation_start_data(request):
    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    files = []
    if hasattr(request, "FILES"):
        files = request.FILES.getlist("temporary_attachments")
        if not files:
            files = request.FILES.getlist("temporary_attachments[]")
    if files:
        if hasattr(data, "setlist"):
            data.setlist("temporary_attachments", files)
        else:
            data["temporary_attachments"] = files
    return data


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


class AIGenerationSessionCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(
            get_generation_session_queryset_for_actor(request.user),
            pk=pk,
        )
        try:
            session = cancel_generation_session(session=session, user=request.user)
        except AIGenerationPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(AIGenerationSessionSerializer(session).data, status=status.HTTP_200_OK)


class AIGenerationSessionClarifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(
            get_generation_session_queryset_for_actor(request.user),
            pk=pk,
        )
        serializer = AIGenerationClarifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = answer_clarification(
                session=session,
                user=request.user,
                answers=serializer.validated_data["answers"],
            )
        except AIGenerationPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except AICapacityExceededError as exc:
            raise Throttled(detail=str(exc)) from exc
        except (ValueError, LLMProviderError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(AIGenerationSessionSerializer(session).data, status=status.HTTP_200_OK)


class AIGenerationSessionRefineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(
            get_generation_session_queryset_for_actor(request.user),
            pk=pk,
        )
        serializer = AIGenerationRefineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = request_draft_refinement(
                session=session,
                user=request.user,
                instruction=serializer.validated_data["instruction"],
                draft_ids=serializer.validated_data.get("draft_ids") or [],
            )
        except AIGenerationPermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except AICapacityExceededError as exc:
            raise Throttled(detail=str(exc)) from exc
        except (ValueError, LLMProviderError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(AIGenerationSessionSerializer(session).data, status=status.HTTP_200_OK)


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


class AIAuthoringScriptSaveView(APIView):
    """Translate a passed AI authoring trace into a runnable Selenium Python
    script and persist it as an ``AutomationScript`` row attached to the same
    test case. The new script becomes the active one for the
    (test_case, framework=selenium, language=python) tuple, so the regression
    pipeline picks it up on the next run."""

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
            script = commit_authoring_trace_as_selenium_script(
                execution=execution,
                user=request.user,
            )
        except AIAuthoringError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            AutomationScriptSerializer(script, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
