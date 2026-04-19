from django.db.models import Count, Prefetch, Q

from apps.projects.access import can_manage_project_record, get_project_queryset_for_actor
from apps.projects.models import ProjectMember, ProjectMemberRole
from apps.specs.models import Specification
from apps.testing.models import (
    TestCase,
    TestCaseRevision,
    TestScenario,
    TestSection,
    TestSuite,
)


SPECIFICATION_TRACEABILITY_QUERYSET = Specification.objects.only(
    "id",
    "title",
    "external_reference",
    "source_type",
    "project_id",
).order_by("external_reference", "title")

TEST_CASE_REVISION_TRACEABILITY_QUERYSET = TestCaseRevision.objects.select_related(
    "created_by",
).prefetch_related(
    Prefetch("linked_specifications", queryset=SPECIFICATION_TRACEABILITY_QUERYSET)
).order_by("-version_number", "-created_at")

TEST_CASE_TRACEABILITY_QUERYSET = TestCase.objects.select_related(
    "scenario",
    "scenario__section",
    "scenario__section__suite",
    "scenario__section__suite__project",
).prefetch_related(
    Prefetch("linked_specifications", queryset=SPECIFICATION_TRACEABILITY_QUERYSET),
    Prefetch("revisions", queryset=TEST_CASE_REVISION_TRACEABILITY_QUERYSET),
).order_by("scenario__title", "order_index", "title")

TEST_SCENARIO_TRACEABILITY_QUERYSET = TestScenario.objects.select_related(
    "section",
    "section__suite",
    "section__suite__project",
    "section__suite__specification",
).prefetch_related(
    Prefetch("cases", queryset=TEST_CASE_TRACEABILITY_QUERYSET)
).order_by("section__order_index", "order_index", "title")

TEST_SECTION_TRACEABILITY_QUERYSET = TestSection.objects.select_related(
    "suite",
    "suite__project",
    "suite__specification",
    "parent",
).prefetch_related(
    Prefetch("scenarios", queryset=TEST_SCENARIO_TRACEABILITY_QUERYSET)
).order_by("order_index", "name")


def _get_project_member(user, project):
    return ProjectMember.objects.filter(
        project=project,
        user=user,
    ).only("role").first()


def can_view_test_design_for_project(user, project) -> bool:
    if not user.is_authenticated:
        return False
    return get_project_queryset_for_actor(user).filter(pk=project.pk).exists()


def can_manage_test_design_for_project(user, project) -> bool:
    if can_manage_project_record(user, project):
        return True

    membership = _get_project_member(user, project)
    if membership is None:
        return False

    return membership.role in {
        ProjectMemberRole.OWNER,
        ProjectMemberRole.EDITOR,
    }


def can_create_test_suite(user, project) -> bool:
    return can_manage_test_design_for_project(user, project)


def can_create_test_section(user, suite: TestSuite) -> bool:
    return can_manage_test_suite_record(user, suite)


def can_create_test_scenario(user, container) -> bool:
    suite = container.suite if isinstance(container, TestSection) else container
    return can_manage_test_suite_record(user, suite)


def can_create_test_case(user, scenario: TestScenario) -> bool:
    return can_manage_test_scenario_record(user, scenario)


def can_view_test_suite_record(user, suite: TestSuite) -> bool:
    return can_view_test_design_for_project(user, suite.project)


def can_manage_test_suite_record(user, suite: TestSuite) -> bool:
    return can_manage_test_design_for_project(user, suite.project)


def can_view_test_section_record(user, section: TestSection) -> bool:
    return can_view_test_suite_record(user, section.suite)


def can_manage_test_section_record(user, section: TestSection) -> bool:
    return can_manage_test_suite_record(user, section.suite)


def can_view_test_scenario_record(user, scenario: TestScenario) -> bool:
    return can_view_test_section_record(user, scenario.section)


def can_manage_test_scenario_record(user, scenario: TestScenario) -> bool:
    return can_manage_test_section_record(user, scenario.section)


def can_view_test_case_record(user, test_case: TestCase) -> bool:
    return can_view_test_scenario_record(user, test_case.scenario)


def can_manage_test_case_record(user, test_case: TestCase) -> bool:
    return can_manage_test_scenario_record(user, test_case.scenario)


def can_view_test_case_revision_record(user, revision: TestCaseRevision) -> bool:
    return can_view_test_case_record(user, revision.test_case)


def get_test_suite_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return TestSuite.objects.select_related(
        "project",
        "project__team",
        "project__team__organization",
        "specification",
        "created_by",
    ).prefetch_related(
        Prefetch("sections", queryset=TEST_SECTION_TRACEABILITY_QUERYSET)
    ).annotate(
        section_count=Count("sections", distinct=True),
        scenario_count=Count("sections__scenarios", distinct=True),
        total_case_count=Count("sections__scenarios__cases", distinct=True),
        passed_case_count=Count(
            "sections__scenarios__cases",
            filter=Q(sections__scenarios__cases__executions__result__status="passed"),
            distinct=True,
        ),
        linked_specification_count=Count(
            "sections__scenarios__cases__linked_specifications",
            distinct=True,
        ),
    ).filter(project__in=project_queryset).order_by(
        "project__name",
        "folder_path",
        "name",
    )


def get_test_section_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return TestSection.objects.select_related(
        "suite",
        "suite__project",
        "suite__specification",
        "parent",
    ).prefetch_related(
        Prefetch("scenarios", queryset=TEST_SCENARIO_TRACEABILITY_QUERYSET)
    ).annotate(
        scenario_count=Count("scenarios", distinct=True),
        total_case_count=Count("scenarios__cases", distinct=True),
        linked_specification_count=Count(
            "scenarios__cases__linked_specifications",
            distinct=True,
        ),
    ).filter(suite__project__in=project_queryset).order_by(
        "suite__name",
        "order_index",
        "name",
    )


def get_test_scenario_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return TestScenario.objects.select_related(
        "section",
        "section__suite",
        "section__suite__project",
        "section__suite__specification",
    ).prefetch_related(
        Prefetch("cases", queryset=TEST_CASE_TRACEABILITY_QUERYSET)
    ).annotate(
        case_count=Count("cases", distinct=True),
        passed_case_count=Count(
            "cases",
            filter=Q(cases__executions__result__status="passed"),
            distinct=True,
        ),
        linked_specification_count=Count(
            "cases__linked_specifications",
            distinct=True,
        ),
    ).filter(section__suite__project__in=project_queryset).order_by(
        "section__suite__name",
        "section__order_index",
        "order_index",
        "title",
    )


def get_test_case_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return TestCase.objects.select_related(
        "scenario",
        "scenario__section",
        "scenario__section__suite",
        "scenario__section__suite__project",
    ).prefetch_related(
        Prefetch("linked_specifications", queryset=SPECIFICATION_TRACEABILITY_QUERYSET),
        Prefetch("revisions", queryset=TEST_CASE_REVISION_TRACEABILITY_QUERYSET),
    ).filter(scenario__section__suite__project__in=project_queryset).order_by(
        "scenario__title",
        "order_index",
        "title",
    )


def get_test_case_revision_queryset_for_actor(actor):
    return TestCaseRevision.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
        "created_by",
    ).prefetch_related(
        Prefetch("linked_specifications", queryset=SPECIFICATION_TRACEABILITY_QUERYSET)
    ).filter(
        test_case__in=get_test_case_queryset_for_actor(actor)
    ).order_by("-version_number", "-created_at")
