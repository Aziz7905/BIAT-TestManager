from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.testing.serializers import (
    TestCaseSerializer,
    TestCaseWriteSerializer,
    TestScenarioSerializer,
    TestScenarioWriteSerializer,
    TestSuiteSerializer,
)
from apps.testing.services import (
    can_manage_test_case_record,
    can_manage_test_scenario_record,
    can_manage_test_suite_record,
    can_view_test_case_record,
    can_view_test_scenario_record,
    can_view_test_suite_record,
    get_test_case_queryset_for_actor,
    get_test_scenario_queryset_for_actor,
    get_test_suite_queryset_for_actor,
)


class TestSuiteListCreateView(generics.ListCreateAPIView):
    serializer_class = TestSuiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_test_suite_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        specification_id = self.request.query_params.get("specification")
        if specification_id:
            queryset = queryset.filter(
                Q(specification_id=specification_id)
                | Q(scenarios__cases__linked_specifications=specification_id)
            ).distinct()
        return queryset


class TestSuiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestSuiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_test_suite_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        suite = self.get_object()
        if not can_view_test_suite_record(request.user, suite):
            raise PermissionDenied("You do not have permission to view this test suite.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        suite = self.get_object()
        if not can_manage_test_suite_record(request.user, suite):
            raise PermissionDenied("You do not have permission to update this test suite.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        suite = self.get_object()
        if not can_manage_test_suite_record(request.user, suite):
            raise PermissionDenied("You do not have permission to delete this test suite.")
        return super().destroy(request, *args, **kwargs)


class TestScenarioListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_suite(self):
        return get_object_or_404(
            get_test_suite_queryset_for_actor(self.request.user),
            pk=self.kwargs["suite_pk"],
        )

    def get_queryset(self):
        suite = self.get_suite()
        return get_test_scenario_queryset_for_actor(self.request.user).filter(suite=suite)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context

    def list(self, request, *args, **kwargs):
        suite = self.get_suite()
        if not can_view_test_suite_record(request.user, suite):
            raise PermissionDenied("You do not have permission to view this suite's scenarios.")
        return super().list(request, *args, **kwargs)


class TestScenarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "scenario_pk"

    def get_suite(self):
        return get_object_or_404(
            get_test_suite_queryset_for_actor(self.request.user),
            pk=self.kwargs["suite_pk"],
        )

    def get_queryset(self):
        suite = self.get_suite()
        return get_test_scenario_queryset_for_actor(self.request.user).filter(suite=suite)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context

    def retrieve(self, request, *args, **kwargs):
        scenario = self.get_object()
        if not can_view_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to view this scenario.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        scenario = self.get_object()
        if not can_manage_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to update this scenario.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        scenario = self.get_object()
        if not can_manage_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to delete this scenario.")
        return super().destroy(request, *args, **kwargs)


class TestScenarioCloneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scenario_pk):
        scenario = get_object_or_404(
            get_test_scenario_queryset_for_actor(request.user),
            pk=scenario_pk,
        )
        if not can_manage_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to clone this scenario.")

        cloned_scenario = scenario.clone()
        serializer = TestScenarioSerializer(cloned_scenario, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TestCaseListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_scenario(self):
        return get_object_or_404(
            get_test_scenario_queryset_for_actor(self.request.user),
            pk=self.kwargs["scenario_pk"],
        )

    def get_queryset(self):
        scenario = self.get_scenario()
        return get_test_case_queryset_for_actor(self.request.user).filter(scenario=scenario)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestCaseWriteSerializer
        return TestCaseSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["scenario"] = self.get_scenario()
        return context

    def list(self, request, *args, **kwargs):
        scenario = self.get_scenario()
        if not can_view_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to view this scenario's test cases.")
        return super().list(request, *args, **kwargs)


class TestCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "case_pk"

    def get_scenario(self):
        return get_object_or_404(
            get_test_scenario_queryset_for_actor(self.request.user),
            pk=self.kwargs["scenario_pk"],
        )

    def get_queryset(self):
        scenario = self.get_scenario()
        return get_test_case_queryset_for_actor(self.request.user).filter(scenario=scenario)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TestCaseWriteSerializer
        return TestCaseSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["scenario"] = self.get_scenario()
        return context

    def retrieve(self, request, *args, **kwargs):
        test_case = self.get_object()
        if not can_view_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to view this test case.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        test_case = self.get_object()
        if not can_manage_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to update this test case.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        test_case = self.get_object()
        if not can_manage_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to delete this test case.")
        return super().destroy(request, *args, **kwargs)
