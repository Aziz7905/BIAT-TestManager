from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.providers.brain import get_team_brain
from apps.ai.services.capacity import check_ai_generation_capacity
from apps.ai.workflows.generation.attachments import extract_temporary_attachment_context
from apps.ai.workflows.generation.events import append_generation_event
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
    selected_specifications=None,
    temporary_attachments=None,
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

    resolved_source_refs = _build_source_refs(
        source_refs or {},
        selected_specifications=selected_specifications or [],
        temporary_attachments=temporary_attachments or [],
    )

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
        source_refs=resolved_source_refs,
        jira_issue_key=jira_issue_key or "",
        provider_name=provider.name,
        model_name=provider.model_name,
        purpose=ModelProfilePurpose.TEST_DESIGN,
        schema_version=SCHEMA_VERSION,
    )
    append_generation_event(
        session,
        "session_started",
        message="Generation session queued.",
        payload={
            "temporary_attachment_count": len(
                resolved_source_refs.get("temporary_attachments") or []
            ),
            "selected_specification_count": len(
                resolved_source_refs.get("selected_specification_ids") or []
            ),
        },
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
        AIGenerationSessionStatus.FAILED,
    }:
        raise ValueError("Only ready or partially generated AI sessions can be reviewed.")

    session.review_decisions = decisions
    session.status = AIGenerationSessionStatus.REVIEWING
    session.save(update_fields=["review_decisions", "status", "updated_at"])
    return session


def answer_clarification(
    *,
    session: AIGenerationSession,
    user,
    answers: str,
) -> AIGenerationSession:
    """Fold the requester's clarification into the objective and re-run generation."""
    if not can_manage_test_design_for_project(user, session.project):
        raise AIGenerationPermissionError(
            "You do not have permission to answer this AI generation session."
        )
    if session.status != AIGenerationSessionStatus.CLARIFICATION_REQUIRED:
        raise ValueError("Only sessions awaiting clarification can be answered.")

    cleaned = (answers or "").strip()
    if not cleaned:
        raise ValueError("Clarification answer cannot be empty.")

    check_ai_generation_capacity(session.project.team)

    refs = dict(session.source_refs or {})
    base_objective = str(refs.get("base_objective") or session.objective or "").strip()
    history = list(refs.get("clarification_answers") or [])
    history.append({"answer": cleaned, "answered_at": timezone.now().isoformat()})
    refs["base_objective"] = base_objective
    refs["clarification_answers"] = history

    session.source_refs = refs
    session.objective = _augment_objective_with_clarifications(base_objective, history)
    session.status = AIGenerationSessionStatus.QUEUED
    session.draft_payload = {}
    session.completed_at = None
    session.save(
        update_fields=[
            "source_refs",
            "objective",
            "status",
            "draft_payload",
            "completed_at",
            "updated_at",
        ]
    )
    append_generation_event(
        session,
        "clarification_answered",
        message="Clarification received. Regenerating with the new details.",
        payload={"answer": cleaned},
    )

    from apps.ai.tasks import enqueue_generation_session_task

    enqueue_generation_session_task(str(session.id))
    session.refresh_from_db()
    return session


def request_draft_refinement(
    *,
    session: AIGenerationSession,
    user,
    instruction: str,
    draft_ids: list[str] | None = None,
) -> AIGenerationSession:
    """Queue a single-pass LLM patch of the ready draft from a reviewer instruction."""
    if not can_manage_test_design_for_project(user, session.project):
        raise AIGenerationPermissionError(
            "You do not have permission to refine this AI generation session."
        )
    if session.status not in {
        AIGenerationSessionStatus.READY_FOR_REVIEW,
        AIGenerationSessionStatus.REVIEWING,
    }:
        raise ValueError("Only a draft that is ready for review can be refined.")

    cleaned = (instruction or "").strip()
    if not cleaned:
        raise ValueError("Refinement instruction cannot be empty.")
    if not isinstance(session.draft_payload, dict) or not session.draft_payload.get("sections"):
        raise ValueError("There is no draft to refine yet.")

    focus_ids = [str(item) for item in (draft_ids or []) if str(item).strip()]

    session.status = AIGenerationSessionStatus.GENERATING
    session.save(update_fields=["status", "updated_at"])
    append_generation_event(
        session,
        "refine_requested",
        message="Applying your requested changes to the draft.",
        payload={"instruction": cleaned, "focus_count": len(focus_ids)},
    )

    from apps.ai.tasks import enqueue_generation_refine_task

    enqueue_generation_refine_task(str(session.id), cleaned, focus_ids)
    session.refresh_from_db()
    return session


def _augment_objective_with_clarifications(
    base_objective: str,
    history: list[dict[str, Any]],
) -> str:
    if not history:
        return base_objective
    lines = [f"- {item.get('answer', '').strip()}" for item in history if item.get("answer")]
    if not lines:
        return base_objective
    return (
        f"{base_objective}\n\n"
        "Additional clarifications from the requester:\n" + "\n".join(lines)
    )


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
    append_generation_event(session, "generation_cancelled", message="Generation was cancelled.")
    return session


def _build_source_refs(
    source_refs: dict[str, Any],
    *,
    selected_specifications,
    temporary_attachments,
) -> dict[str, Any]:
    refs = dict(source_refs or {})
    selected_ids = [str(specification.id) for specification in selected_specifications]
    if selected_ids:
        existing = refs.get("selected_specification_ids")
        merged = []
        if isinstance(existing, list):
            merged.extend(str(item) for item in existing if item)
        merged.extend(selected_ids)
        refs["selected_specification_ids"] = sorted(set(merged))

    extracted_attachments = []
    for uploaded_file in temporary_attachments:
        context = extract_temporary_attachment_context(uploaded_file)
        extracted_attachments.append(
            {
                "attachment_id": context.attachment_id,
                "filename": context.filename,
                "file_type": context.file_type,
                "fragments": context.fragments,
                "source_metadata": context.source_metadata,
            }
        )
    if extracted_attachments:
        refs["temporary_attachments"] = extracted_attachments
    return refs
