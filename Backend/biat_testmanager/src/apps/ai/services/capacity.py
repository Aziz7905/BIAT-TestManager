from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus

DEFAULT_MAX_CONCURRENT_AI_GENERATIONS = 20
ACTIVE_GENERATION_STATUSES = [
    AIGenerationSessionStatus.QUEUED,
    AIGenerationSessionStatus.GENERATING,
    AIGenerationSessionStatus.READY_FOR_REVIEW,
    AIGenerationSessionStatus.REVIEWING,
]


class AICapacityExceededError(Exception):
    """Raised when a team has too many active AI generation sessions."""


@dataclass(frozen=True)
class CapacityCheckResult:
    active_count: int
    max_active: int

    @property
    def allowed(self) -> bool:
        return self.active_count < self.max_active


def check_ai_generation_capacity(
    team,
    *,
    exclude_session_id: str | None = None,
) -> CapacityCheckResult:
    max_active = int(
        getattr(
            settings,
            "AI_MAX_CONCURRENT_GENERATION_SESSIONS_PER_TEAM",
            DEFAULT_MAX_CONCURRENT_AI_GENERATIONS,
        )
    )
    queryset = AIGenerationSession.objects.filter(
        team=team,
        status__in=ACTIVE_GENERATION_STATUSES,
    )
    if exclude_session_id:
        queryset = queryset.exclude(pk=exclude_session_id)
    active_count = queryset.count()
    result = CapacityCheckResult(active_count=active_count, max_active=max_active)
    if not result.allowed:
        raise AICapacityExceededError(
            f"Team AI generation capacity exceeded ({active_count}/{max_active})."
        )
    return result
