from django.contrib.auth import get_user_model

from apps.accounts.models import Team
from apps.accounts.services.memberships import sync_team_manager_membership

User = get_user_model()


def sync_manager_profile_with_team(manager_user: User | None, team: Team) -> None:  # type: ignore[type-arg]
    sync_team_manager_membership(team, manager_user)
