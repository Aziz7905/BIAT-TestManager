from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.access import get_project_queryset_for_actor
from apps.testing.models import TestPlan, TestRun, TestRunCase, TestRunCaseStatus
from apps.testing.serializers import (
    TestPlanSerializer,
    TestRunCaseSerializer,
    TestRunExpandSerializer,
    TestRunSerializer,
)
from apps.testing.services.access import can_manage_test_design_for_project
from apps.testing.services.runs import archive_test_plan, close_test_run, start_test_run


def _plan_queryset(actor):
    project_qs = get_project_queryset_for_actor(actor)
    return TestPlan.objects.select_related(
        "project", "project__team", "created_by"
    ).annotate(
        run_count=Count("runs", distinct=True),
    ).filter(project__in=project_qs).order_by("-created_at")


def _run_queryset(actor):
    project_qs = get_project_queryset_for_actor(actor)
    return TestRun.objects.select_related(
        "project", "project__team", "plan", "created_by"
    ).annotate(
        run_case_count=Count("run_cases", distinct=True),
        passed_case_count=Count(
            "run_cases",
            filter=Q(run_cases__status=TestRunCaseStatus.PASSED),
            distinct=True,
        ),
    ).filter(project__in=project_qs).order_by("-created_at")


def _run_case_queryset(actor):
    project_qs = get_project_queryset_for_actor(actor)
    return TestRunCase.objects.select_related(
        "run",
        "run__project",
        "test_case",
        "test_case_revision",
        "assigned_to",
    ).filter(run__project__in=project_qs).order_by("run", "order_index")


class TestPlanListCreateView(generics.ListCreateAPIView):
    serializer_class = TestPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = _plan_queryset(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class TestPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _plan_queryset(self.request.user)

    def perform_destroy(self, instance):
        if not can_manage_test_design_for_project(self.request.user, instance.project):
            raise PermissionDenied
        archive_test_plan(instance)


class TestPlanRunListView(generics.ListAPIView):
    """List all runs under a specific plan."""
    serializer_class = TestRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_queryset(self.request.user).filter(plan_id=self.kwargs["plan_pk"])


class TestRunListCreateView(generics.ListCreateAPIView):
    serializer_class = TestRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = _run_queryset(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        return qs


class TestRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_queryset(self.request.user)

    def perform_destroy(self, instance):
        if not can_manage_test_design_for_project(self.request.user, instance.project):
            raise PermissionDenied
        instance.delete()


class TestRunStartView(APIView):
    """Mark a run as running."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied
        updated = start_test_run(run)
        return Response(TestRunSerializer(updated, context={"request": request}).data)


class TestRunCloseView(APIView):
    """Derive and set the terminal status of a run from its run-case outcomes."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied
        updated = close_test_run(run)
        return Response(TestRunSerializer(updated, context={"request": request}).data)


class TestRunExpandView(APIView):
    """Expand a run by adding run-cases from a suite, section, or explicit case list."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied

        serializer = TestRunExpandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run_cases = serializer.expand(run)

        return Response(
            {
                "created_count": len(run_cases),
                "run_case_count": run.run_cases.count(),
            },
            status=status.HTTP_201_CREATED,
        )


class TestRunCaseListView(generics.ListAPIView):
    serializer_class = TestRunCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_case_queryset(self.request.user).filter(run_id=self.kwargs["run_pk"])


class TestRunCaseDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TestRunCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_case_queryset(self.request.user)
