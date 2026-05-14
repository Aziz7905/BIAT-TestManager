from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.providers.brain import get_team_brain
from apps.ai.services.capacity import check_ai_generation_capacity
from apps.ai.workflows.generation.schemas import SCHEMA_VERSION
from apps.projects.access import get_project_queryset_for_actor
from apps.testing.services.access import can_manage_test_design_for_project


class AIGenerationPermissionError(PermissionError):
    """Raised when a user cannot access or mutate an AI generation session."""


def get_generation_session_queryset_for_actor(actor):
    return AIGenerationSession.objects.select_related(
        "team",
        "project",
        "project__team",
        "created_by",
        "target_suite",
        "target_section",
        "attached_specification",
    ).prefetch_related("retrieved_contexts").filter(
        project__in=get_project_queryset_for_actor(actor)
    )


def start_generation_session(
    *,
    user,
    project,
    objective: str,
    source_type: str,
    target_suite=None,
    target_section=None,
    attached_specification=None,
    source_refs: dict[str, Any] | None = None,
    jira_issue_key: str = "",
) -> AIGenerationSession:
    if not can_manage_test_design_for_project(user, project):
        raise AIGenerationPermissionError(
            "You do not have permission to generate tests for this project."
        )

    check_ai_generation_capacity(project.team)
    provider = get_team_brain(project.team, purpose=ModelProfilePurpose.TEST_DESIGN)

    from apps.ai.tasks import enqueue_generation_session_task

    session = AIGenerationSession.objects.create(
        team=project.team,
        project=project,
        created_by=user,
        target_suite=target_suite,
        target_section=target_section,
        attached_specification=attached_specification,
        status=AIGenerationSessionStatus.QUEUED,
        source_type=source_type,
        objective=objective,
        source_refs=source_refs or {},
        jira_issue_key=jira_issue_key or "",
        provider_name=provider.name,
        model_name=provider.model_name,
        purpose=ModelProfilePurpose.TEST_DESIGN,
        schema_version=SCHEMA_VERSION,
    )
    enqueue_generation_session_task(str(session.id))
    return session


def apply_review_decisions(
    *,
    session: AIGenerationSession,
    decisions: dict[str, Any],
    user,
) -> AIGenerationSession:
    if session.created_by_id != user.id and not can_manage_test_design_for_project(
        user,
        session.project,
    ):
        raise AIGenerationPermissionError(
            "You do not have permission to review this AI generation session."
        )
    if session.status not in {
        AIGenerationSessionStatus.READY_FOR_REVIEW,
        AIGenerationSessionStatus.REVIEWING,
    }:
        raise ValueError("Only ready AI generation sessions can be reviewed.")

    session.review_decisions = decisions
    session.status = AIGenerationSessionStatus.REVIEWING
    session.save(update_fields=["review_decisions", "status", "updated_at"])
    return session


def cancel_generation_session(*, session: AIGenerationSession, user) -> AIGenerationSession:
    if not can_manage_test_design_for_project(user, session.project):
        raise AIGenerationPermissionError(
            "You do not have permission to cancel this AI generation session."
        )
    if session.status in {
        AIGenerationSessionStatus.SAVED,
        AIGenerationSessionStatus.FAILED,
        AIGenerationSessionStatus.CANCELLED,
    }:
        return session
    session.status = AIGenerationSessionStatus.CANCELLED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])
    return session
