from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.automation.models import AutomationScript, ExecutionSchedule, TestExecution
from apps.automation.models.choices import ExecutionStatus
from apps.automation.serializers import (
    AutomationScriptDetailSerializer,
    AutomationScriptSerializer,
    AutomationScriptWriteSerializer,
    ExecutionScheduleSerializer,
    ExecutionStepSerializer,
    TestExecutionCreateSerializer,
    TestExecutionSerializer,
    TestResultSerializer,
)
from apps.automation.services import (
    can_manage_automation_script_record,
    can_manage_execution_schedule_record,
    can_manage_test_execution_record,
    can_view_automation_script_record,
    can_view_execution_schedule_record,
    can_view_test_execution_record,
    create_and_queue_execution,
    get_automation_script_queryset_for_actor,
    get_execution_schedule_queryset_for_actor,
    get_execution_step_queryset_for_actor,
    get_test_execution_queryset_for_actor,
    get_test_result_queryset_for_actor,
    request_execution_pause,
    request_execution_resume,
    request_execution_stop,
)


class AutomationScriptListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_automation_script_queryset_for_actor(self.request.user)
        test_case_id = self.request.query_params.get("test_case")
        if test_case_id:
            queryset = queryset.filter(test_case_id=test_case_id)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AutomationScriptWriteSerializer
        return AutomationScriptSerializer


class AutomationScriptDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_automation_script_queryset_for_actor(self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return AutomationScriptWriteSerializer
        return AutomationScriptDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        script = self.get_object()
        if not can_view_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to view this automation script.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        script = self.get_object()
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to update this automation script.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        script = self.get_object()
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to delete this automation script.")
        return super().destroy(request, *args, **kwargs)


class AutomationScriptActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        script = get_object_or_404(get_automation_script_queryset_for_actor(request.user), pk=pk)
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to activate this automation script.")

        script.is_active = True
        script.save(update_fields=["is_active"])
        serializer = AutomationScriptDetailSerializer(
            script,
            context={"request": request},
        )
        return Response(serializer.data)


class AutomationScriptDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        script = get_object_or_404(get_automation_script_queryset_for_actor(request.user), pk=pk)
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to deactivate this automation script.")

        script.is_active = False
        script.save(update_fields=["is_active"])
        serializer = AutomationScriptDetailSerializer(
            script,
            context={"request": request},
        )
        return Response(serializer.data)


class AutomationScriptValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        script = get_object_or_404(get_automation_script_queryset_for_actor(request.user), pk=pk)
        if not can_view_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to validate this automation script.")
        return Response(script.validate_syntax())


class TestExecutionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_test_execution_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        suite_id = self.request.query_params.get("suite")
        test_case_id = self.request.query_params.get("test_case")
        status_value = self.request.query_params.get("status")

        if project_id:
            queryset = queryset.filter(test_case__scenario__suite__project_id=project_id)
        if suite_id:
            queryset = queryset.filter(test_case__scenario__suite_id=suite_id)
        if test_case_id:
            queryset = queryset.filter(test_case_id=test_case_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestExecutionCreateSerializer
        return TestExecutionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        execution = create_and_queue_execution(
            test_case=serializer.validated_data["test_case"],
            triggered_by=request.user,
            trigger_type=serializer.validated_data.get("trigger_type", "manual"),
            browser=serializer.validated_data.get("browser", "chromium"),
            platform=serializer.validated_data.get("platform", "desktop"),
            script=serializer.validated_data.get("script"),
        )
        response_serializer = TestExecutionSerializer(execution, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class TestExecutionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = TestExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_test_execution_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        execution = self.get_object()
        if not can_view_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to view this execution.")
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        execution = self.get_object()
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to delete this execution.")
        if execution.status not in {
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.CANCELLED,
        }:
            raise PermissionDenied(
                "Only failed, errored, or cancelled executions can be deleted."
            )
        return super().destroy(request, *args, **kwargs)


class TestExecutionPauseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(get_test_execution_queryset_for_actor(request.user), pk=pk)
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to pause this execution.")
        serializer = TestExecutionSerializer(request_execution_pause(execution), context={"request": request})
        return Response(serializer.data)


class TestExecutionResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(get_test_execution_queryset_for_actor(request.user), pk=pk)
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to resume this execution.")
        serializer = TestExecutionSerializer(request_execution_resume(execution), context={"request": request})
        return Response(serializer.data)


class TestExecutionStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(get_test_execution_queryset_for_actor(request.user), pk=pk)
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to stop this execution.")
        serializer = TestExecutionSerializer(request_execution_stop(execution), context={"request": request})
        return Response(serializer.data)


class ExecutionStepListView(generics.ListAPIView):
    serializer_class = ExecutionStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_execution_step_queryset_for_actor(self.request.user).filter(
            execution_id=self.kwargs["execution_pk"]
        )


class ExecutionStepDetailView(generics.RetrieveAPIView):
    serializer_class = ExecutionStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_execution_step_queryset_for_actor(self.request.user).filter(
            execution_id=self.kwargs["execution_pk"]
        )


class TestResultDetailView(generics.RetrieveAPIView):
    serializer_class = TestResultSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        execution = get_object_or_404(
            get_test_execution_queryset_for_actor(self.request.user),
            pk=self.kwargs["execution_pk"],
        )
        if not can_view_test_execution_record(self.request.user, execution):
            raise PermissionDenied("You do not have permission to view this execution result.")
        return get_object_or_404(get_test_result_queryset_for_actor(self.request.user), execution=execution)


class TestResultExportJunitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, execution_pk):
        execution = get_object_or_404(
            get_test_execution_queryset_for_actor(request.user),
            pk=execution_pk,
        )
        if not can_view_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to export this execution result.")
        result = get_object_or_404(get_test_result_queryset_for_actor(request.user), execution=execution)
        return Response({"junit_xml": result.export_junit_xml()})


class ExecutionScheduleListCreateView(generics.ListCreateAPIView):
    serializer_class = ExecutionScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_execution_schedule_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        suite_id = self.request.query_params.get("suite")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if suite_id:
            queryset = queryset.filter(suite_id=suite_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ExecutionScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExecutionScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_execution_schedule_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        schedule = self.get_object()
        if not can_view_execution_schedule_record(request.user, schedule):
            raise PermissionDenied("You do not have permission to view this schedule.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        schedule = self.get_object()
        if not can_manage_execution_schedule_record(request.user, schedule):
            raise PermissionDenied("You do not have permission to update this schedule.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        schedule = self.get_object()
        if not can_manage_execution_schedule_record(request.user, schedule):
            raise PermissionDenied("You do not have permission to delete this schedule.")
        return super().destroy(request, *args, **kwargs)


class ExecutionScheduleTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(get_execution_schedule_queryset_for_actor(request.user), pk=pk)
        if not can_manage_execution_schedule_record(request.user, schedule):
            raise PermissionDenied("You do not have permission to trigger this schedule.")
        executions = schedule.trigger_now()
        serializer = TestExecutionSerializer(executions, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
