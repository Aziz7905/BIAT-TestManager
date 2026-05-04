from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.access import get_project_queryset_for_actor
from apps.testing.models import TestPlan, TestRun, TestRunCase, TestRunCaseStatus, TestRunKind
from apps.testing.serializers import (
    TestPlanSerializer,
    TestRunCaseSerializer,
    TestRunExpandSerializer,
    TestRunSerializer,
)
from apps.testing.services.access import can_manage_test_design_for_project
from apps.testing.services.runs import (
    archive_test_plan,
    close_test_run,
    execute_pending_run_cases,
    rerun_failed_run_cases,
    start_test_run,
)


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
        from apps.testing.models import TestPlanStatus

        if not can_manage_test_design_for_project(self.request.user, instance.project):
            raise PermissionDenied("You do not have permission to delete this test plan.")
        if instance.status == TestPlanStatus.ARCHIVED:
            instance.delete()
        else:
            archive_test_plan(instance)


class TestPlanRunListView(generics.ListAPIView):
    """List all runs under a specific plan."""
    serializer_class = TestRunSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        include_system = self.request.query_params.get("include_system", "").lower() in ("1", "true", "yes")
        if not include_system:
            qs = qs.exclude(run_kind=TestRunKind.SYSTEM_GENERATED)
        return qs


class TestRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_queryset(self.request.user)

    def perform_destroy(self, instance):
        if not can_manage_test_design_for_project(self.request.user, instance.project):
            raise PermissionDenied("You do not have permission to delete this test run.")
        instance.delete()


class TestRunStartView(APIView):
    """Mark a run as running."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied("You do not have permission to start this test run.")
        updated = start_test_run(run)
        return Response(TestRunSerializer(updated, context={"request": request}).data)


class TestRunCloseView(APIView):
    """Derive and set the terminal status of a run from its run-case outcomes."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied("You do not have permission to close this test run.")
        updated = close_test_run(run)
        return Response(TestRunSerializer(updated, context={"request": request}).data)


class TestRunExpandView(APIView):
    """Expand a run by adding run-cases from a suite, section, or explicit case list."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied("You do not have permission to expand this test run.")

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
    pagination_class = None

    def get_queryset(self):
        return _run_case_queryset(self.request.user).filter(run_id=self.kwargs["run_pk"])


class TestRunCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestRunCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _run_case_queryset(self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if not can_manage_test_design_for_project(self.request.user, instance.run.project):
            raise PermissionDenied("You do not have permission to update this run case.")
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError

        if not can_manage_test_design_for_project(self.request.user, instance.run.project):
            raise PermissionDenied("You do not have permission to remove this run case.")
        if instance.status != TestRunCaseStatus.PENDING:
            raise ValidationError(
                "Run cases can only be removed while pending — protect execution history."
            )
        if instance.executions.exists():
            raise ValidationError(
                "This run case has executions and cannot be removed — protect execution history."
            )
        instance.delete()


class TestRunExecuteView(APIView):
    """Trigger automated execution for every pending run-case in this run.

    Each pending case dispatches one TestExecution through the existing
    automation pipeline, reusing the case's active AutomationScript.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied("You do not have permission to run this test run.")

        browser = request.data.get("browser") or None
        platform = request.data.get("platform") or None

        executions = execute_pending_run_cases(
            run,
            triggered_by=request.user,
            browser=browser,
            platform=platform,
        )
        return Response(
            {
                "queued_count": len(executions),
                "execution_ids": [str(execution.id) for execution in executions],
            },
            status=status.HTTP_201_CREATED,
        )


class TestRunRerunFailedView(APIView):
    """Reset failed run-cases to pending and re-queue executions for them."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        run = generics.get_object_or_404(_run_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run.project):
            raise PermissionDenied("You do not have permission to re-run this run.")

        browser = request.data.get("browser") or None
        platform = request.data.get("platform") or None

        executions = rerun_failed_run_cases(
            run,
            triggered_by=request.user,
            browser=browser,
            platform=platform,
        )
        return Response(
            {
                "queued_count": len(executions),
                "execution_ids": [str(execution.id) for execution in executions],
            },
            status=status.HTTP_201_CREATED,
        )


class TestRunCaseExecuteView(APIView):
    """Trigger an automated execution for a specific run case.

    Reuses the existing automation pipeline — creates a queued TestExecution
    tied to this run_case so progress and results stream back into the
    Test Runs workspace.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.automation.models.choices import (
            ExecutionBrowser,
            ExecutionPlatform,
            ExecutionTriggerType,
        )
        from apps.automation.services import create_execution_record, queue_execution

        run_case = generics.get_object_or_404(_run_case_queryset(request.user), pk=pk)
        if not can_manage_test_design_for_project(request.user, run_case.run.project):
            raise PermissionDenied("You do not have permission to run this case.")
        if run_case.test_case_id is None:
            return Response(
                {"detail": "This run-case no longer has a linked test case."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        browser = request.data.get("browser") or ExecutionBrowser.CHROMIUM
        platform = request.data.get("platform") or ExecutionPlatform.DESKTOP

        execution = create_execution_record(
            test_case=run_case.test_case,
            triggered_by=request.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser=browser,
            platform=platform,
            run_case=run_case,
        )
        queue_execution(execution)

        run_case.refresh_from_db()
        return Response(
            TestRunCaseSerializer(run_case, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
