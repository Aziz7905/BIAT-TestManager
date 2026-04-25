from django.urls import path

from apps.testing.views import (
    ProjectDashboardOverviewView,
    ProjectFailureHotspotsView,
    ProjectPassRateTrendView,
    ProjectRepositoryOverviewView,
    TestPlanDetailView,
    TestPlanListCreateView,
    TestPlanRunListView,
    TestRunCaseDetailView,
    TestRunCaseExecuteView,
    TestRunCaseListView,
    TestRunCloseView,
    TestRunDetailView,
    TestRunExpandView,
    TestRunListCreateView,
    TestRunStartView,
    TestCaseApproveView,
    TestCaseArchiveView,
    TestCaseCloneView,
    TestCaseDetailView,
    TestCaseListCreateView,
    TestCaseRevisionDetailView,
    TestCaseRevisionListView,
    TestCaseWorkspaceView,
    TestScenarioCloneView,
    TestScenarioDetailView,
    TestScenarioListCreateView,
    TestScenarioOverviewView,
    TestSectionDetailView,
    TestSectionListCreateView,
    TestSectionOverviewView,
    TestSectionScenarioDetailView,
    TestSectionScenarioListCreateView,
    TestSuiteDetailView,
    TestSuiteListCreateView,
    TestSuiteOverviewView,
)

urlpatterns = [
    # Reporting / dashboard
    path(
        "projects/<uuid:project_pk>/reporting/overview/",
        ProjectDashboardOverviewView.as_view(),
        name="project-reporting-overview",
    ),
    path(
        "projects/<uuid:project_pk>/reporting/pass-rate-trend/",
        ProjectPassRateTrendView.as_view(),
        name="project-reporting-pass-rate-trend",
    ),
    path(
        "projects/<uuid:project_pk>/reporting/failure-hotspots/",
        ProjectFailureHotspotsView.as_view(),
        name="project-reporting-failure-hotspots",
    ),
    path(
        "projects/<uuid:project_pk>/repository/overview/",
        ProjectRepositoryOverviewView.as_view(),
        name="project-repository-overview",
    ),
    # Plans
    path("test-plans/", TestPlanListCreateView.as_view(), name="test-plan-list-create"),
    path("test-plans/<uuid:pk>/", TestPlanDetailView.as_view(), name="test-plan-detail"),
    path("test-plans/<uuid:plan_pk>/runs/", TestPlanRunListView.as_view(), name="test-plan-run-list"),
    # Runs
    path("test-runs/", TestRunListCreateView.as_view(), name="test-run-list-create"),
    path("test-runs/<uuid:pk>/", TestRunDetailView.as_view(), name="test-run-detail"),
    path("test-runs/<uuid:pk>/start/", TestRunStartView.as_view(), name="test-run-start"),
    path("test-runs/<uuid:pk>/close/", TestRunCloseView.as_view(), name="test-run-close"),
    path("test-runs/<uuid:pk>/expand/", TestRunExpandView.as_view(), name="test-run-expand"),
    path("test-runs/<uuid:run_pk>/cases/", TestRunCaseListView.as_view(), name="test-run-case-list"),
    path("test-run-cases/<uuid:pk>/", TestRunCaseDetailView.as_view(), name="test-run-case-detail"),
    path(
        "test-run-cases/<uuid:pk>/execute/",
        TestRunCaseExecuteView.as_view(),
        name="test-run-case-execute",
    ),
    # Suites
    path("test-suites/", TestSuiteListCreateView.as_view(), name="test-suite-list-create"),
    path("test-suites/<uuid:pk>/", TestSuiteDetailView.as_view(), name="test-suite-detail"),
    path(
        "test-suites/<uuid:suite_pk>/overview/",
        TestSuiteOverviewView.as_view(),
        name="test-suite-overview",
    ),
    path(
        "test-suites/<uuid:suite_pk>/sections/",
        TestSectionListCreateView.as_view(),
        name="test-section-list-create",
    ),
    path(
        "test-suites/<uuid:suite_pk>/sections/<uuid:section_pk>/",
        TestSectionDetailView.as_view(),
        name="test-section-detail",
    ),
    path(
        "test-sections/<uuid:section_pk>/overview/",
        TestSectionOverviewView.as_view(),
        name="test-section-overview",
    ),
    path(
        "test-suites/<uuid:suite_pk>/scenarios/",
        TestScenarioListCreateView.as_view(),
        name="test-scenario-list-create",
    ),
    path(
        "test-suites/<uuid:suite_pk>/scenarios/<uuid:scenario_pk>/",
        TestScenarioDetailView.as_view(),
        name="test-scenario-detail",
    ),
    path(
        "test-sections/<uuid:section_pk>/scenarios/",
        TestSectionScenarioListCreateView.as_view(),
        name="test-section-scenario-list-create",
    ),
    path(
        "test-sections/<uuid:section_pk>/scenarios/<uuid:scenario_pk>/",
        TestSectionScenarioDetailView.as_view(),
        name="test-section-scenario-detail",
    ),
    path(
        "test-scenarios/<uuid:scenario_pk>/overview/",
        TestScenarioOverviewView.as_view(),
        name="test-scenario-overview",
    ),
    path(
        "test-scenarios/<uuid:scenario_pk>/clone/",
        TestScenarioCloneView.as_view(),
        name="test-scenario-clone",
    ),
    path(
        "test-scenarios/<uuid:scenario_pk>/cases/",
        TestCaseListCreateView.as_view(),
        name="test-case-list-create",
    ),
    path(
        "test-scenarios/<uuid:scenario_pk>/cases/<uuid:case_pk>/",
        TestCaseDetailView.as_view(),
        name="test-case-detail",
    ),
    path(
        "test-cases/<uuid:case_pk>/revisions/",
        TestCaseRevisionListView.as_view(),
        name="test-case-revision-list",
    ),
    path(
        "test-cases/<uuid:case_pk>/workspace/",
        TestCaseWorkspaceView.as_view(),
        name="test-case-workspace",
    ),
    path(
        "test-cases/<uuid:case_pk>/revisions/<uuid:revision_pk>/",
        TestCaseRevisionDetailView.as_view(),
        name="test-case-revision-detail",
    ),
    # Design-status workflow actions
    path(
        "test-cases/<uuid:case_pk>/approve/",
        TestCaseApproveView.as_view(),
        name="test-case-approve",
    ),
    path(
        "test-cases/<uuid:case_pk>/archive/",
        TestCaseArchiveView.as_view(),
        name="test-case-archive",
    ),
    path(
        "test-cases/<uuid:case_pk>/clone/",
        TestCaseCloneView.as_view(),
        name="test-case-clone",
    ),
]
