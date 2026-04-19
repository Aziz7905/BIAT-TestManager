from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone

from apps.automation.models import (
    AutomationScript,
    TestArtifact,
    TestExecution,
    TestResult,
)
from apps.projects.models import Project
from apps.specs.models import Specification
from apps.testing.models import TestCase, TestScenario, TestSection, TestSuite
from apps.testing.models.choices import (
    TestCaseAutomationStatus,
    TestCaseDesignStatus,
)
from apps.testing.models.utils import calculate_pass_rate
from apps.testing.services.reporting import list_project_recent_run_cards


RECENT_ACTIVITY_DAYS = 14
LINKED_SPECIFICATION_PREVIEW_LIMIT = 12
REPOSITORY_TOP_SUITE_LIMIT = 5
CASE_RECENT_RESULTS_LIMIT = 5


def get_repository_tree_suites(project: Project):
    scenario_queryset = TestScenario.objects.annotate(
        case_count=Count("cases", distinct=True),
        approved_case_count=Count(
            "cases",
            filter=Q(cases__design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "cases",
            filter=Q(cases__automation_status=TestCaseAutomationStatus.AUTOMATED),
            distinct=True,
        ),
    ).order_by("order_index", "title")

    section_queryset = TestSection.objects.annotate(
        child_section_count=Count("children", distinct=True),
        scenario_count=Count("scenarios", distinct=True),
        case_count=Count("scenarios__cases", distinct=True),
    ).prefetch_related(
        Prefetch("scenarios", queryset=scenario_queryset)
    ).order_by("order_index", "name")

    return TestSuite.objects.filter(project=project).annotate(
        section_count=Count("sections", distinct=True),
        scenario_count=Count("sections__scenarios", distinct=True),
        case_count=Count("sections__scenarios__cases", distinct=True),
    ).prefetch_related(
        Prefetch("sections", queryset=section_queryset)
    ).order_by("folder_path", "name")


def build_project_repository_tree_summary(project: Project) -> dict[str, int]:
    summary = TestCase.objects.filter(
        scenario__section__suite__project=project
    ).aggregate(
        case_count=Count("id", distinct=True),
        approved_case_count=Count(
            "id",
            filter=Q(design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "id",
            filter=Q(automation_status=TestCaseAutomationStatus.AUTOMATED),
            distinct=True,
        ),
    )
    return {
        "suite_count": TestSuite.objects.filter(project=project).count(),
        "scenario_count": TestScenario.objects.filter(section__suite__project=project).count(),
        "case_count": summary["case_count"] or 0,
        "approved_case_count": summary["approved_case_count"] or 0,
        "automated_case_count": summary["automated_case_count"] or 0,
    }


def get_repository_case_summary_queryset(*, scenario: TestScenario):
    latest_result_queryset = TestResult.objects.filter(
        execution__test_case=OuterRef("pk")
    ).order_by("-created_at")
    return TestCase.objects.filter(scenario=scenario).annotate(
        latest_result_status=Subquery(latest_result_queryset.values("status")[:1]),
        has_active_script=Exists(
            AutomationScript.objects.filter(
                test_case=OuterRef("pk"),
                is_active=True,
            )
        ),
    ).order_by("order_index", "title")


def build_project_repository_overview(project: Project) -> dict:
    summary = _build_case_summary_counts(
        TestCase.objects.filter(scenario__section__suite__project=project)
    )
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "team_name": project.team.name,
            "organization_name": project.team.organization.name,
        },
        "summary": {
            "suite_count": TestSuite.objects.filter(project=project).count(),
            "section_count": TestSection.objects.filter(suite__project=project).count(),
            "scenario_count": TestScenario.objects.filter(section__suite__project=project).count(),
            **summary,
        },
        "recent_activity": _build_recent_activity_snapshot(
            TestResult.objects.filter(execution__test_case__scenario__section__suite__project=project)
        ),
        "top_suites": [
            {
                "id": suite.id,
                "name": suite.name,
                "folder_path": suite.folder_path,
                "counts": {
                    "scenario_count": suite.scenario_count or 0,
                    "case_count": suite.case_count or 0,
                    "approved_case_count": suite.approved_case_count or 0,
                    "automated_case_count": suite.automated_case_count or 0,
                },
            }
            for suite in TestSuite.objects.filter(project=project).annotate(
                scenario_count=Count("sections__scenarios", distinct=True),
                case_count=Count("sections__scenarios__cases", distinct=True),
                approved_case_count=Count(
                    "sections__scenarios__cases",
                    filter=Q(
                        sections__scenarios__cases__design_status=TestCaseDesignStatus.APPROVED,
                    ),
                    distinct=True,
                ),
                automated_case_count=Count(
                    "sections__scenarios__cases",
                    filter=Q(
                        sections__scenarios__cases__automation_status=(
                            TestCaseAutomationStatus.AUTOMATED
                        ),
                    ),
                    distinct=True,
                ),
            ).order_by("-case_count", "folder_path", "name")[:REPOSITORY_TOP_SUITE_LIMIT]
        ],
        "recent_runs": list_project_recent_run_cards(project, limit=5),
    }


def build_test_suite_overview(suite: TestSuite) -> dict:
    section_preview_queryset = TestSection.objects.filter(
        suite=suite,
        parent__isnull=True,
    ).annotate(
        child_section_count=Count("children", distinct=True),
        scenario_count=Count("scenarios", distinct=True),
        case_count=Count("scenarios__cases", distinct=True),
        approved_case_count=Count(
            "scenarios__cases",
            filter=Q(scenarios__cases__design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "scenarios__cases",
            filter=Q(
                scenarios__cases__automation_status=TestCaseAutomationStatus.AUTOMATED
            ),
            distinct=True,
        ),
    ).order_by("order_index", "name")

    counts = _build_case_summary_counts(
        TestCase.objects.filter(scenario__section__suite=suite)
    )
    return {
        "id": suite.id,
        "name": suite.name,
        "description": suite.description,
        "folder_path": suite.folder_path,
        "context": {
            "project_id": suite.project_id,
            "project_name": suite.project.name,
        },
        "specification": _serialize_specification(suite.specification),
        "created_by_name": _display_user_name(suite.created_by),
        "created_at": suite.created_at,
        "counts": {
            "section_count": suite.sections.count(),
            "scenario_count": TestScenario.objects.filter(section__suite=suite).count(),
            **counts,
        },
        "recent_activity": _build_recent_activity_snapshot(
            TestResult.objects.filter(execution__test_case__scenario__section__suite=suite)
        ),
        "linked_specifications": _serialize_specification_queryset(
            Specification.objects.filter(
                linked_test_cases__scenario__section__suite=suite
            ).distinct()[:LINKED_SPECIFICATION_PREVIEW_LIMIT]
        ),
        "sections": [
            {
                "id": section.id,
                "name": section.name,
                "counts": {
                    "child_section_count": section.child_section_count or 0,
                    "scenario_count": section.scenario_count or 0,
                    "case_count": section.case_count or 0,
                    "approved_case_count": section.approved_case_count or 0,
                    "automated_case_count": section.automated_case_count or 0,
                },
            }
            for section in section_preview_queryset
        ],
    }


def build_test_section_overview(section: TestSection) -> dict:
    child_sections = TestSection.objects.filter(parent=section).annotate(
        child_section_count=Count("children", distinct=True),
        scenario_count=Count("scenarios", distinct=True),
        case_count=Count("scenarios__cases", distinct=True),
        approved_case_count=Count(
            "scenarios__cases",
            filter=Q(scenarios__cases__design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "scenarios__cases",
            filter=Q(
                scenarios__cases__automation_status=TestCaseAutomationStatus.AUTOMATED
            ),
            distinct=True,
        ),
    ).order_by("order_index", "name")

    scenarios = TestScenario.objects.filter(section=section).annotate(
        case_count=Count("cases", distinct=True),
        approved_case_count=Count(
            "cases",
            filter=Q(cases__design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "cases",
            filter=Q(cases__automation_status=TestCaseAutomationStatus.AUTOMATED),
            distinct=True,
        ),
    ).order_by("order_index", "title")

    counts = _build_case_summary_counts(TestCase.objects.filter(scenario__section=section))
    return {
        "id": section.id,
        "name": section.name,
        "context": {
            "project_id": section.suite.project_id,
            "project_name": section.suite.project.name,
            "suite_id": section.suite_id,
            "suite_name": section.suite.name,
            "parent_id": section.parent_id,
            "parent_name": section.parent.name if section.parent_id else None,
        },
        "counts": {
            "child_section_count": child_sections.count(),
            "scenario_count": scenarios.count(),
            **counts,
        },
        "recent_activity": _build_recent_activity_snapshot(
            TestResult.objects.filter(execution__test_case__scenario__section=section)
        ),
        "linked_specifications": _serialize_specification_queryset(
            Specification.objects.filter(
                linked_test_cases__scenario__section=section
            ).distinct()[:LINKED_SPECIFICATION_PREVIEW_LIMIT]
        ),
        "child_sections": [
            {
                "id": child.id,
                "name": child.name,
                "counts": {
                    "child_section_count": child.child_section_count or 0,
                    "scenario_count": child.scenario_count or 0,
                    "case_count": child.case_count or 0,
                    "approved_case_count": child.approved_case_count or 0,
                    "automated_case_count": child.automated_case_count or 0,
                },
            }
            for child in child_sections
        ],
        "scenarios": [
            {
                "id": scenario.id,
                "title": scenario.title,
                "priority": scenario.priority,
                "scenario_type": scenario.scenario_type,
                "counts": {
                    "case_count": scenario.case_count or 0,
                    "approved_case_count": scenario.approved_case_count or 0,
                    "automated_case_count": scenario.automated_case_count or 0,
                },
            }
            for scenario in scenarios
        ],
    }


def build_test_scenario_overview(scenario: TestScenario) -> dict:
    case_queryset = get_repository_case_summary_queryset(scenario=scenario)
    counts = _build_case_summary_counts(TestCase.objects.filter(scenario=scenario))
    return {
        "id": scenario.id,
        "title": scenario.title,
        "description": scenario.description,
        "scenario_type": scenario.scenario_type,
        "priority": scenario.priority,
        "business_priority": scenario.business_priority,
        "polarity": scenario.polarity,
        "context": {
            "project_id": scenario.suite.project_id,
            "project_name": scenario.suite.project.name,
            "suite_id": scenario.suite_id,
            "suite_name": scenario.suite.name,
            "section_id": scenario.section_id,
            "section_name": scenario.section.name,
        },
        "coverage": counts,
        "execution_snapshot": _build_recent_activity_snapshot(
            TestResult.objects.filter(execution__test_case__scenario=scenario)
        ),
        "linked_specifications": _serialize_specification_queryset(
            Specification.objects.filter(
                linked_test_cases__scenario=scenario
            ).distinct()[:LINKED_SPECIFICATION_PREVIEW_LIMIT]
        ),
        "cases": [
            {
                "id": test_case.id,
                "title": test_case.title,
                "design_status": test_case.design_status,
                "automation_status": test_case.automation_status,
                "version": test_case.version,
                "order_index": test_case.order_index,
                "latest_result_status": test_case.latest_result_status,
                "has_active_script": bool(test_case.has_active_script),
            }
            for test_case in case_queryset
        ],
    }


def build_test_case_workspace(test_case: TestCase) -> dict:
    active_scripts = list(
        AutomationScript.objects.filter(
            test_case=test_case,
            is_active=True,
        ).order_by("framework", "language", "-script_version")
    )
    latest_execution = (
        TestExecution.objects.filter(test_case=test_case)
        .select_related("result", "script")
        .prefetch_related("artifacts")
        .order_by("-started_at", "-id")
        .first()
    )
    recent_results = list(
        TestResult.objects.filter(execution__test_case=test_case)
        .select_related("execution")
        .order_by("-created_at")[:CASE_RECENT_RESULTS_LIMIT]
    )
    artifact_summary = TestArtifact.objects.filter(execution__test_case=test_case).aggregate(
        artifact_count=Count("id"),
        last_artifact_at=Max("created_at"),
    )

    revisions = list(test_case.revisions.select_related("created_by").order_by("-version_number", "-created_at"))
    return {
        "id": test_case.id,
        "title": test_case.title,
        "context": {
            "project_id": test_case.scenario.section.suite.project_id,
            "project_name": test_case.scenario.section.suite.project.name,
            "suite_id": test_case.scenario.section.suite_id,
            "suite_name": test_case.scenario.section.suite.name,
            "section_id": test_case.scenario.section_id,
            "section_name": test_case.scenario.section.name,
            "scenario_id": test_case.scenario_id,
            "scenario_title": test_case.scenario.title,
        },
        "design": {
            "preconditions": test_case.preconditions,
            "steps": test_case.steps,
            "expected_result": test_case.expected_result,
            "test_data": test_case.test_data,
            "design_status": test_case.design_status,
            "automation_status": test_case.automation_status,
            "jira_issue_key": test_case.jira_issue_key,
            "on_failure": test_case.on_failure,
            "timeout_ms": test_case.timeout_ms,
            "version": test_case.version,
            "current_revision_id": str(revisions[0].id) if revisions else None,
            "linked_specifications": _serialize_specification_queryset(
                test_case.linked_specifications.all()
            ),
            "created_at": test_case.created_at,
            "updated_at": test_case.updated_at,
        },
        "automation": {
            "has_active_script": bool(active_scripts),
            "active_script_count": len(active_scripts),
            "runnable_frameworks": sorted({script.framework for script in active_scripts}),
            "latest_execution": _serialize_latest_execution(latest_execution),
            "artifact_count": artifact_summary["artifact_count"] or 0,
            "last_artifact_at": artifact_summary["last_artifact_at"],
        },
        "history": {
            "version_history": [
                {
                    "id": revision.id,
                    "version_number": revision.version_number,
                    "created_by": revision.created_by_id,
                    "created_by_name": _display_user_name(revision.created_by),
                    "created_at": revision.created_at,
                }
                for revision in revisions
            ],
            "recent_results": [
                {
                    "execution_id": result.execution_id,
                    "status": result.status,
                    "created_at": result.created_at,
                    "duration_ms": result.duration_ms,
                }
                for result in recent_results
            ],
        },
    }


def _build_case_summary_counts(queryset) -> dict[str, int]:
    summary = queryset.aggregate(
        case_count=Count("id", distinct=True),
        approved_case_count=Count(
            "id",
            filter=Q(design_status=TestCaseDesignStatus.APPROVED),
            distinct=True,
        ),
        automated_case_count=Count(
            "id",
            filter=Q(automation_status=TestCaseAutomationStatus.AUTOMATED),
            distinct=True,
        ),
        draft_case_count=Count(
            "id",
            filter=Q(design_status=TestCaseDesignStatus.DRAFT),
            distinct=True,
        ),
        in_review_case_count=Count(
            "id",
            filter=Q(design_status=TestCaseDesignStatus.IN_REVIEW),
            distinct=True,
        ),
        archived_case_count=Count(
            "id",
            filter=Q(design_status=TestCaseDesignStatus.ARCHIVED),
            distinct=True,
        ),
        manual_case_count=Count(
            "id",
            filter=Q(automation_status=TestCaseAutomationStatus.MANUAL),
            distinct=True,
        ),
    )
    return {key: value or 0 for key, value in summary.items()}


def _build_recent_activity_snapshot(result_queryset) -> dict:
    recent_since = timezone.now() - timedelta(days=RECENT_ACTIVITY_DAYS)
    aggregates = result_queryset.aggregate(
        last_execution_at=Max("created_at"),
        recent_execution_count=Count(
            "id",
            filter=Q(created_at__gte=recent_since),
        ),
        recent_passed_results=Count(
            "id",
            filter=Q(created_at__gte=recent_since, status="passed"),
        ),
    )
    recent_execution_count = aggregates["recent_execution_count"] or 0
    recent_passed_results = aggregates["recent_passed_results"] or 0
    return {
        "last_execution_at": aggregates["last_execution_at"],
        "recent_execution_count": recent_execution_count,
        "recent_pass_rate": calculate_pass_rate(
            total_count=recent_execution_count,
            passed_count=recent_passed_results,
        ),
    }


def _serialize_specification_queryset(queryset) -> list[dict]:
    return [
        {
            "id": specification.id,
            "title": specification.title,
            "external_reference": specification.external_reference,
            "source_type": specification.source_type,
        }
        for specification in queryset
    ]


def _serialize_specification(specification) -> dict | None:
    if specification is None:
        return None
    return {
        "id": specification.id,
        "title": specification.title,
        "external_reference": specification.external_reference,
        "source_type": specification.source_type,
    }


def _serialize_latest_execution(execution: TestExecution | None) -> dict | None:
    if execution is None:
        return None

    result = getattr(execution, "result", None)
    return {
        "id": execution.id,
        "status": result.status if result is not None else execution.status,
        "started_at": execution.started_at,
        "ended_at": execution.ended_at,
        "duration_ms": result.duration_ms if result is not None else execution.get_duration_ms(),
        "browser": execution.browser,
        "platform": execution.platform,
        "framework": execution.script.framework if execution.script_id else None,
        "artifact_count": execution.artifacts.count(),
    }


def _display_user_name(user) -> str | None:
    if user is None:
        return None
    full_name = user.get_full_name().strip()
    return full_name or user.email or user.username
