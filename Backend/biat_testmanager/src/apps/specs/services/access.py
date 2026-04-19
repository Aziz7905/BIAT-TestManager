from django.db.models import Count, Prefetch, Q

from apps.projects.access import can_manage_project_record, get_project_queryset_for_actor
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import SpecChunk, Specification, SpecificationSource, SpecificationSourceRecord
from apps.testing.models import TestCase


LINKED_TEST_CASE_PREVIEW_QUERYSET = TestCase.objects.select_related(
    "scenario",
    "scenario__section",
    "scenario__section__suite",
).only(
    "id",
    "title",
    "design_status",
    "automation_status",
    "version",
    "scenario__id",
    "scenario__title",
    "scenario__section__suite__id",
    "scenario__section__suite__name",
).order_by("scenario__section__suite__name", "scenario__title", "title")

SPEC_CHUNK_QUERYSET = SpecChunk.objects.select_related("embedding_model_config").order_by(
    "chunk_index"
)


def can_view_specifications(user) -> bool:
    return user.is_authenticated


def _has_project_spec_write_access(user, project: Project) -> bool:
    if can_manage_project_record(user, project):
        return True

    return ProjectMember.objects.filter(
        project=project,
        user=user,
        role__in=[ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR],
    ).exists()


def can_create_specifications(user, project: Project) -> bool:
    return _has_project_spec_write_access(user, project)


def can_manage_specification_record(user, specification: Specification) -> bool:
    return _has_project_spec_write_access(user, specification.project)


def can_manage_specification_source(user, source: SpecificationSource) -> bool:
    return _has_project_spec_write_access(user, source.project)


def can_manage_specification_source_record(user, record: SpecificationSourceRecord) -> bool:
    return _has_project_spec_write_access(user, record.source.project)


def get_specification_queryset_for_actor(actor):
    visible_projects = get_project_queryset_for_actor(actor)
    return (
        Specification.objects.select_related(
            "project",
            "project__team",
            "project__team__organization",
            "uploaded_by",
            "source",
        )
        .prefetch_related(
            Prefetch("chunks", queryset=SPEC_CHUNK_QUERYSET),
            Prefetch("linked_test_cases", queryset=LINKED_TEST_CASE_PREVIEW_QUERYSET),
        )
        .annotate(
            chunk_count=Count("chunks", distinct=True),
            linked_test_case_count=Count("linked_test_cases", distinct=True),
            linked_scenario_count=Count(
                "linked_test_cases__scenario",
                distinct=True,
            ),
            linked_suite_count=Count(
                "linked_test_cases__scenario__section__suite",
                distinct=True,
            ),
        )
        .filter(project__in=visible_projects)
        .order_by("project__name", "title", "-created_at")
    )


def get_specification_source_queryset_for_actor(actor):
    visible_projects = get_project_queryset_for_actor(actor).values_list("id", flat=True)
    return (
        SpecificationSource.objects.select_related(
            "project",
            "project__team",
            "project__team__organization",
            "uploaded_by",
        )
        .prefetch_related("records")
        .annotate(
            record_count=Count("records"),
            selected_record_count=Count("records", filter=Q(records__is_selected=True)),
            imported_record_count=Count(
                "records",
                filter=Q(records__linked_specification__isnull=False),
            ),
        )
        .filter(project_id__in=visible_projects)
        .order_by("-created_at", "name")
    )
