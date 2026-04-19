from __future__ import annotations

from apps.accounts.models import (
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
)


def get_organization_role(user) -> str | None:
    profile = getattr(user, "profile", None)
    return getattr(profile, "organization_role", None)


def get_effective_user_role(user, *, team: Team | None = None) -> str | None:
    profile = getattr(user, "profile", None)
    if not profile:
        return None

    organization_role = getattr(profile, "organization_role", None)
    if organization_role in {
        OrganizationRole.PLATFORM_OWNER,
        OrganizationRole.ORG_ADMIN,
    }:
        return organization_role

    membership_queryset = TeamMembership.objects.filter(user=user, is_active=True)
    if team is not None:
        membership_queryset = membership_queryset.filter(team=team)

    memberships = list(membership_queryset.order_by("-is_primary", "joined_at"))
    if any(membership.role == TeamMembershipRole.MANAGER for membership in memberships):
        return TeamMembershipRole.MANAGER

    primary_membership = next(
        (membership for membership in memberships if membership.is_primary),
        memberships[0] if memberships else None,
    )
    if primary_membership:
        return primary_membership.role

    return OrganizationRole.MEMBER


def has_team_manager_role(user, team: Team | None = None) -> bool:
    queryset = TeamMembership.objects.filter(
        user=user,
        role=TeamMembershipRole.MANAGER,
        is_active=True,
    )
    if team is not None:
        queryset = queryset.filter(team=team)
    return queryset.exists()
