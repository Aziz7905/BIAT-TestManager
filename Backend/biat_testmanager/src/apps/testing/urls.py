from django.urls import path

from apps.testing.views import (
    TestCaseDetailView,
    TestCaseListCreateView,
    TestScenarioCloneView,
    TestScenarioDetailView,
    TestScenarioListCreateView,
    TestSuiteDetailView,
    TestSuiteListCreateView,
)

urlpatterns = [
    path("test-suites/", TestSuiteListCreateView.as_view(), name="test-suite-list-create"),
    path("test-suites/<uuid:pk>/", TestSuiteDetailView.as_view(), name="test-suite-detail"),
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
]

