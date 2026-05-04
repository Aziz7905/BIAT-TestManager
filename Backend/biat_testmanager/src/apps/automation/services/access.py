from apps.projects.access import can_manage_project_record, get_project_queryset_for_actor
from apps.projects.models import ProjectMember, ProjectMemberRole
from apps.testing.services import (
    can_manage_test_case_record,
    can_view_test_case_record,
)
from apps.automation.models import (
    AutomationScript,
    ExecutionSchedule,
    ExecutionStep,
    TestExecution,
    TestResult,
)


def can_manage_automation_for_project(user, project) -> bool:
    if can_manage_project_record(user, project):
        return True

    membership = ProjectMember.objects.filter(
        project=project,
        user=user,
    ).only("role").first()
    if membership is None:
        return False

    return membership.role in {
        ProjectMemberRole.OWNER,
        ProjectMemberRole.EDITOR,
    }


def can_view_automation_for_project(user, project) -> bool:
    return get_project_queryset_for_actor(user).filter(pk=project.pk).exists()


def can_manage_automation_script_record(user, script: AutomationScript) -> bool:
    return can_manage_test_case_record(user, script.test_case)


def can_view_automation_script_record(user, script: AutomationScript) -> bool:
    return can_view_test_case_record(user, script.test_case)


def can_trigger_test_execution(user, test_case) -> bool:
    return can_manage_test_case_record(user, test_case)


def can_manage_test_execution_record(user, execution: TestExecution) -> bool:
    if execution.triggered_by_id == getattr(user, "id", None):
        return True
    return can_manage_automation_for_project(user, execution.test_case.scenario.suite.project)


def can_view_test_execution_record(user, execution: TestExecution) -> bool:
    return can_view_test_case_record(user, execution.test_case)


def can_manage_execution_schedule_record(user, schedule: ExecutionSchedule) -> bool:
    return can_manage_automation_for_project(user, schedule.project)


def can_view_execution_schedule_record(user, schedule: ExecutionSchedule) -> bool:
    return can_view_automation_for_project(user, schedule.project)


def get_automation_script_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return AutomationScript.objects.select_related(
        "test_case",
        "test_case_revision",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
    ).filter(
        test_case__scenario__section__suite__project__in=project_queryset
    ).order_by(
        "test_case__title",
        "framework",
        "language",
        "-script_version",
    )


def get_test_execution_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
        "run_case",
        "run_case__run",
        "run_case__test_case_revision",
        "environment",
        "script",
        "script__test_case_revision",
        "triggered_by",
        "result",
    ).filter(
        test_case__scenario__section__suite__project__in=project_queryset
    ).order_by("-started_at", "-id")


def get_execution_step_queryset_for_actor(actor):
    return ExecutionStep.objects.select_related(
        "execution",
        "execution__test_case",
        "execution__test_case__scenario",
        "execution__test_case__scenario__section",
        "execution__test_case__scenario__section__suite",
        "execution__test_case__scenario__section__suite__project",
    ).filter(
        execution__in=get_test_execution_queryset_for_actor(actor)
    ).order_by("execution__started_at", "step_index")


def get_test_result_queryset_for_actor(actor):
    return TestResult.objects.select_related(
        "execution",
        "execution__test_case",
        "execution__test_case__scenario",
        "execution__test_case__scenario__section",
        "execution__test_case__scenario__section__suite",
        "execution__test_case__scenario__section__suite__project",
    ).filter(
        execution__in=get_test_execution_queryset_for_actor(actor)
    ).order_by("-created_at")


def get_execution_schedule_queryset_for_actor(actor):
    project_queryset = get_project_queryset_for_actor(actor)
    return ExecutionSchedule.objects.select_related(
        "project",
        "project__team",
        "project__team__organization",
        "suite",
        "created_by",
    ).filter(project__in=project_queryset).order_by("project__name", "name")
