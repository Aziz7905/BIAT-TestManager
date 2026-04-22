from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.automation.models import (
    AutomationScript,
    ExecutionCheckpoint,
    ExecutionSchedule,
    TestExecution,
)
from apps.automation.models.choices import ExecutionStatus, ExecutionTriggerType
from apps.automation.serializers import (
    AutomationScriptDetailSerializer,
    AutomationScriptSerializer,
    AutomationScriptWriteSerializer,
    ExecutionCheckpointSerializer,
    ExecutionScheduleSerializer,
    ExecutionStreamTicketSerializer,
    ExecutionStepSerializer,
    ManualBrowserExecutionCreateSerializer,
    ScheduleTriggerResponseSerializer,
    TestExecutionCreateSerializer,
    TestExecutionSerializer,
    TestResultSerializer,
)
from apps.automation.services import (
    activate_script,
    can_manage_automation_script_record,
    can_manage_execution_schedule_record,
    can_manage_test_execution_record,
    can_view_automation_script_record,
    can_view_execution_schedule_record,
    can_view_test_execution_record,
    create_and_queue_execution,
    create_and_queue_manual_browser_execution,
    deactivate_script,
    get_automation_script_queryset_for_actor,
    get_execution_schedule_queryset_for_actor,
    get_execution_step_queryset_for_actor,
    get_test_execution_queryset_for_actor,
    get_test_result_queryset_for_actor,
    issue_execution_stream_ticket,
    request_execution_pause,
    request_execution_resume,
    request_execution_stop,
    resume_execution_checkpoint,
    trigger_execution_schedule,
)
from apps.automation.services.control import ExecutionControlUnavailable


class ExecutionControlUnavailableApiError(APIException):
    status_code = 503
    default_detail = "Execution control channel is unavailable."
    default_code = "execution_control_unavailable"


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

    def perform_update(self, serializer):
        script = self.get_object()
        if not can_manage_automation_script_record(self.request.user, script):
            raise PermissionDenied("You do not have permission to update this automation script.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_automation_script_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this automation script.")
        instance.delete()


class AutomationScriptActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        script = get_object_or_404(get_automation_script_queryset_for_actor(request.user), pk=pk)
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to activate this automation script.")
        serializer = AutomationScriptDetailSerializer(
            activate_script(script),
            context={"request": request},
        )
        return Response(serializer.data)


class AutomationScriptDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        script = get_object_or_404(get_automation_script_queryset_for_actor(request.user), pk=pk)
        if not can_manage_automation_script_record(request.user, script):
            raise PermissionDenied("You do not have permission to deactivate this automation script.")
        serializer = AutomationScriptDetailSerializer(
            deactivate_script(script),
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
        trigger_type = self.request.query_params.get("trigger_type")
        include_diagnostic = self.request.query_params.get("include_diagnostic") in {
            "1",
            "true",
            "yes",
        }

        if project_id:
            queryset = queryset.filter(
                test_case__scenario__section__suite__project_id=project_id
            )
        if suite_id:
            queryset = queryset.filter(test_case__scenario__section__suite_id=suite_id)
        if test_case_id:
            queryset = queryset.filter(test_case_id=test_case_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        elif not include_diagnostic:
            queryset = queryset.exclude(trigger_type=ExecutionTriggerType.DIAGNOSTIC)
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
            trigger_type=serializer.validated_data["trigger_type"],
            browser=serializer.validated_data["browser"],
            platform=serializer.validated_data["platform"],
            script=serializer.validated_data.get("script"),
            environment=serializer.validated_data.get("environment"),
        )
        response_serializer = TestExecutionSerializer(execution, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ManualBrowserExecutionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ManualBrowserExecutionCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        execution = create_and_queue_manual_browser_execution(
            test_case=serializer.validated_data["test_case"],
            triggered_by=request.user,
            target_url=serializer.validated_data.get("target_url", ""),
            browser=serializer.validated_data["browser"],
            platform=serializer.validated_data["platform"],
        )
        response_serializer = TestExecutionSerializer(execution, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class TestExecutionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = TestExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_test_execution_queryset_for_actor(self.request.user)

    def perform_destroy(self, instance):
        if not can_manage_test_execution_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this execution.")
        instance.delete()


class TestExecutionPauseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(get_test_execution_queryset_for_actor(request.user), pk=pk)
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to pause this execution.")
        serializer = TestExecutionSerializer(request_execution_pause(execution), context={"request": request})
        return Response(serializer.data)


class TestExecutionStreamTicketView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        execution = get_object_or_404(
            get_test_execution_queryset_for_actor(request.user),
            pk=pk,
        )
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to stream this execution.")
        serializer = ExecutionStreamTicketSerializer(
            issue_execution_stream_ticket(execution, request.user)
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        try:
            stopped = request_execution_stop(execution)
        except ExecutionControlUnavailable as exc:
            raise ExecutionControlUnavailableApiError() from exc
        serializer = TestExecutionSerializer(stopped, context={"request": request})
        return Response(serializer.data)


class ExecutionCheckpointResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, execution_pk, checkpoint_pk):
        execution = get_object_or_404(
            get_test_execution_queryset_for_actor(request.user),
            pk=execution_pk,
        )
        if not can_manage_test_execution_record(request.user, execution):
            raise PermissionDenied("You do not have permission to resume this execution checkpoint.")

        checkpoint = get_object_or_404(
            ExecutionCheckpoint.objects.select_related("execution"),
            pk=checkpoint_pk,
            execution=execution,
        )
        try:
            resumed = resume_execution_checkpoint(checkpoint, resolved_by=request.user)
        except ExecutionControlUnavailable as exc:
            raise ExecutionControlUnavailableApiError() from exc
        serializer = ExecutionCheckpointSerializer(resumed)
        return Response(serializer.data)


class ExecutionStepListView(generics.ListAPIView):
    serializer_class = ExecutionStepSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        return get_object_or_404(get_test_result_queryset_for_actor(self.request.user), execution=execution)


class TestResultExportJunitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, execution_pk):
        execution = get_object_or_404(
            get_test_execution_queryset_for_actor(request.user),
            pk=execution_pk,
        )
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

    def perform_update(self, serializer):
        schedule = self.get_object()
        if not can_manage_execution_schedule_record(self.request.user, schedule):
            raise PermissionDenied("You do not have permission to update this schedule.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_execution_schedule_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this schedule.")
        instance.delete()


class ExecutionScheduleTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        schedule = get_object_or_404(get_execution_schedule_queryset_for_actor(request.user), pk=pk)
        if not can_manage_execution_schedule_record(request.user, schedule):
            raise PermissionDenied("You do not have permission to trigger this schedule.")
        run = trigger_execution_schedule(schedule)
        serializer = ScheduleTriggerResponseSerializer(run, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
