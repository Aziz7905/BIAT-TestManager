#src/app/testing/views/testing.py
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.testing.serializers import (
    RepositoryCaseSummarySerializer,
    TestCaseRevisionSerializer,
    TestCaseSerializer,
    TestCaseWriteSerializer,
    TestScenarioSerializer,
    TestScenarioWriteSerializer,
    TestSectionSerializer,
    TestSectionWriteSerializer,
    TestSuiteSummarySerializer,
    TestSuiteSerializer,
    TestSuiteWriteSerializer,
)
from apps.testing.services import (
    approve_test_case,
    archive_test_case,
    can_manage_test_case_record,
    can_manage_test_scenario_record,
    can_manage_test_section_record,
    can_manage_test_suite_record,
    can_view_test_case_record,
    can_view_test_scenario_record,
    can_view_test_section_record,
    can_view_test_suite_record,
    clone_test_case,
    clone_test_scenario,
    get_repository_case_summary_queryset,
    get_test_case_queryset_for_actor,
    get_test_case_revision_queryset_for_actor,
    get_test_scenario_queryset_for_actor,
    get_test_section_queryset_for_actor,
    get_test_suite_queryset_for_actor,
)


# ---------------------------------------------------------------------------
# TestSuite
# ---------------------------------------------------------------------------

class TestSuiteListCreateView(generics.ListCreateAPIView):
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
                | Q(sections__scenarios__cases__linked_specifications=specification_id)
            ).distinct()
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestSuiteWriteSerializer
        return TestSuiteSummarySerializer


class TestSuiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_test_suite_queryset_for_actor(self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return TestSuiteWriteSerializer
        return TestSuiteSerializer

    def perform_update(self, serializer):
        suite = self.get_object()
        if not can_manage_test_suite_record(self.request.user, suite):
            raise PermissionDenied("You do not have permission to update this test suite.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_test_suite_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this test suite.")
        instance.delete()


# ---------------------------------------------------------------------------
# TestSection
# ---------------------------------------------------------------------------

class TestSectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_suite(self):
        return get_object_or_404(
            get_test_suite_queryset_for_actor(self.request.user),
            pk=self.kwargs["suite_pk"],
        )

    def get_queryset(self):
        suite = self.get_suite()
        return get_test_section_queryset_for_actor(self.request.user).filter(suite=suite)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestSectionWriteSerializer
        return TestSectionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context


class TestSectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "section_pk"

    def get_suite(self):
        return get_object_or_404(
            get_test_suite_queryset_for_actor(self.request.user),
            pk=self.kwargs["suite_pk"],
        )

    def get_queryset(self):
        suite = self.get_suite()
        return get_test_section_queryset_for_actor(self.request.user).filter(suite=suite)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TestSectionWriteSerializer
        return TestSectionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context

    def perform_update(self, serializer):
        section = self.get_object()
        if not can_manage_test_section_record(self.request.user, section):
            raise PermissionDenied("You do not have permission to update this section.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_test_section_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this section.")
        instance.delete()


# ---------------------------------------------------------------------------
# TestScenario (suite-scoped)
# ---------------------------------------------------------------------------

class TestScenarioListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_suite(self):
        return get_object_or_404(
            get_test_suite_queryset_for_actor(self.request.user),
            pk=self.kwargs["suite_pk"],
        )

    def get_queryset(self):
        suite = self.get_suite()
        return get_test_scenario_queryset_for_actor(self.request.user).filter(section__suite=suite)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context


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
        return get_test_scenario_queryset_for_actor(self.request.user).filter(section__suite=suite)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["suite"] = self.get_suite()
        return context

    def perform_update(self, serializer):
        scenario = self.get_object()
        if not can_manage_test_scenario_record(self.request.user, scenario):
            raise PermissionDenied("You do not have permission to update this scenario.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_test_scenario_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this scenario.")
        instance.delete()


# ---------------------------------------------------------------------------
# TestScenario (section-scoped)
# ---------------------------------------------------------------------------

class TestSectionScenarioListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_section(self):
        return get_object_or_404(
            get_test_section_queryset_for_actor(self.request.user),
            pk=self.kwargs["section_pk"],
        )

    def get_queryset(self):
        section = self.get_section()
        return get_test_scenario_queryset_for_actor(self.request.user).filter(section=section)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["section"] = self.get_section()
        return context


class TestSectionScenarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "scenario_pk"

    def get_section(self):
        return get_object_or_404(
            get_test_section_queryset_for_actor(self.request.user),
            pk=self.kwargs["section_pk"],
        )

    def get_queryset(self):
        section = self.get_section()
        return get_test_scenario_queryset_for_actor(self.request.user).filter(section=section)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TestScenarioWriteSerializer
        return TestScenarioSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["section"] = self.get_section()
        return context

    def perform_update(self, serializer):
        scenario = self.get_object()
        if not can_manage_test_scenario_record(self.request.user, scenario):
            raise PermissionDenied("You do not have permission to update this scenario.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_test_scenario_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this scenario.")
        instance.delete()


# ---------------------------------------------------------------------------
# TestScenario — clone action
# ---------------------------------------------------------------------------

class TestScenarioCloneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scenario_pk):
        scenario = get_object_or_404(
            get_test_scenario_queryset_for_actor(request.user),
            pk=scenario_pk,
        )
        if not can_manage_test_scenario_record(request.user, scenario):
            raise PermissionDenied("You do not have permission to clone this scenario.")

        cloned_scenario = clone_test_scenario(scenario)
        serializer = TestScenarioSerializer(cloned_scenario, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------

class TestCaseListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_scenario(self):
        return get_object_or_404(
            get_test_scenario_queryset_for_actor(self.request.user),
            pk=self.kwargs["scenario_pk"],
        )

    def get_queryset(self):
        scenario = self.get_scenario()
        if self.request.method == "GET":
            return get_repository_case_summary_queryset(scenario=scenario)
        return get_test_case_queryset_for_actor(self.request.user).filter(scenario=scenario)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TestCaseWriteSerializer
        return RepositoryCaseSummarySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["scenario"] = self.get_scenario()
        return context


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

    def perform_update(self, serializer):
        test_case = self.get_object()
        if not can_manage_test_case_record(self.request.user, test_case):
            raise PermissionDenied("You do not have permission to update this test case.")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_test_case_record(self.request.user, instance):
            raise PermissionDenied("You do not have permission to delete this test case.")
        instance.delete()


# ---------------------------------------------------------------------------
# TestCase — design-status workflow actions
# ---------------------------------------------------------------------------

class TestCaseApproveView(APIView):
    """Transition a test case to approved design status."""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_pk):
        test_case = get_object_or_404(
            get_test_case_queryset_for_actor(request.user),
            pk=case_pk,
        )
        if not can_manage_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to approve this test case.")
        updated = approve_test_case(test_case)
        return Response(TestCaseSerializer(updated, context={"request": request}).data)


class TestCaseArchiveView(APIView):
    """Transition a test case to archived design status."""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_pk):
        test_case = get_object_or_404(
            get_test_case_queryset_for_actor(request.user),
            pk=case_pk,
        )
        if not can_manage_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to archive this test case.")
        updated = archive_test_case(test_case)
        return Response(TestCaseSerializer(updated, context={"request": request}).data)


class TestCaseCloneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, case_pk):
        test_case = get_object_or_404(
            get_test_case_queryset_for_actor(request.user).prefetch_related(
                "linked_specifications"
            ),
            pk=case_pk,
        )
        if not can_manage_test_case_record(request.user, test_case):
            raise PermissionDenied("You do not have permission to clone this test case.")

        cloned_case = clone_test_case(test_case, created_by=request.user)
        cloned_summary = get_object_or_404(
            get_repository_case_summary_queryset(scenario=cloned_case.scenario),
            pk=cloned_case.pk,
        )
        serializer = RepositoryCaseSummarySerializer(cloned_summary)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# TestCaseRevision
# ---------------------------------------------------------------------------

class TestCaseRevisionListView(generics.ListAPIView):
    serializer_class = TestCaseRevisionSerializer
    permission_classes = [IsAuthenticated]

    def get_case(self):
        return get_object_or_404(
            get_test_case_queryset_for_actor(self.request.user),
            pk=self.kwargs["case_pk"],
        )

    def get_queryset(self):
        test_case = self.get_case()
        return get_test_case_revision_queryset_for_actor(self.request.user).filter(
            test_case=test_case
        )


class TestCaseRevisionDetailView(generics.RetrieveAPIView):
    serializer_class = TestCaseRevisionSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "revision_pk"

    def get_case(self):
        return get_object_or_404(
            get_test_case_queryset_for_actor(self.request.user),
            pk=self.kwargs["case_pk"],
        )

    def get_queryset(self):
        test_case = self.get_case()
        return get_test_case_revision_queryset_for_actor(self.request.user).filter(
            test_case=test_case
        )
