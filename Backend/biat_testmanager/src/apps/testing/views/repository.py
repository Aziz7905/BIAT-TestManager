from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.access import get_project_queryset_for_actor
from apps.testing.models import TestCase, TestScenario, TestSection, TestSuite
from apps.testing.serializers.repository import (
    ProjectRepositoryOverviewSerializer,
    TestCaseWorkspaceSerializer,
    TestScenarioOverviewSerializer,
    TestSectionOverviewSerializer,
    TestSuiteOverviewSerializer,
)
from apps.testing.services.repository_queries import (
    build_project_repository_overview,
    build_test_case_workspace,
    build_test_scenario_overview,
    build_test_section_overview,
    build_test_suite_overview,
)


class ProjectRepositoryOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_pk):
        project = get_object_or_404(
            get_project_queryset_for_actor(request.user),
            pk=project_pk,
        )
        serializer = ProjectRepositoryOverviewSerializer(
            build_project_repository_overview(project)
        )
        return Response(serializer.data)


class TestSuiteOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, suite_pk):
        suite = get_object_or_404(
            TestSuite.objects.select_related("project", "project__team", "specification", "created_by"),
            pk=suite_pk,
            project__in=get_project_queryset_for_actor(request.user),
        )
        serializer = TestSuiteOverviewSerializer(build_test_suite_overview(suite))
        return Response(serializer.data)


class TestSectionOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, section_pk):
        section = get_object_or_404(
            TestSection.objects.select_related(
                "suite",
                "suite__project",
                "suite__project__team",
                "parent",
            ),
            pk=section_pk,
            suite__project__in=get_project_queryset_for_actor(request.user),
        )
        serializer = TestSectionOverviewSerializer(build_test_section_overview(section))
        return Response(serializer.data)


class TestScenarioOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, scenario_pk):
        scenario = get_object_or_404(
            TestScenario.objects.select_related(
                "section",
                "section__suite",
                "section__suite__project",
            ),
            pk=scenario_pk,
            section__suite__project__in=get_project_queryset_for_actor(request.user),
        )
        serializer = TestScenarioOverviewSerializer(build_test_scenario_overview(scenario))
        return Response(serializer.data)


class TestCaseWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, case_pk):
        test_case = get_object_or_404(
            TestCase.objects.select_related(
                "scenario",
                "scenario__section",
                "scenario__section__suite",
                "scenario__section__suite__project",
            ).prefetch_related(
                "linked_specifications",
                "revisions__created_by",
            ),
            pk=case_pk,
            scenario__section__suite__project__in=get_project_queryset_for_actor(request.user),
        )
        serializer = TestCaseWorkspaceSerializer(build_test_case_workspace(test_case))
        return Response(serializer.data)
