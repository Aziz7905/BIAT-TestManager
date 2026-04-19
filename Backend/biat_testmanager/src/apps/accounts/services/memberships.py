from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import (
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
)

User = get_user_model()


def get_active_team_memberships_for_user(user: User):  # type: ignore[type-arg]
    return TeamMembership.objects.filter(user=user, is_active=True).select_related(
        "team",
        "team__organization",
    )


def get_primary_team_membership_for_user(user: User):  # type: ignore[type-arg]
    memberships = get_active_team_memberships_for_user(user)
    return memberships.filter(is_primary=True).first() or memberships.first()


def _ensure_member_organization_role(user: User | None) -> None:  # type: ignore[type-arg]
    if not user:
        return

    profile = getattr(user, "profile", None)
    if not profile:
        return

    if profile.organization_role not in {
        OrganizationRole.PLATFORM_OWNER,
        OrganizationRole.ORG_ADMIN,
    }:
        if profile.organization_role != OrganizationRole.MEMBER:
            profile.organization_role = OrganizationRole.MEMBER
            profile.save(update_fields=["organization_role"])


@transaction.atomic
def upsert_team_membership(
    user: User,  # type: ignore[type-arg]
    team: Team,
    role: str,
    *,
    is_primary: bool = False,
) -> TeamMembership:
    membership, _ = TeamMembership.objects.get_or_create(
        user=user,
        team=team,
        defaults={
            "role": role,
            "is_primary": is_primary,
            "is_active": True,
        },
    )

    update_fields: list[str] = []

    if membership.role != role:
        membership.role = role
        update_fields.append("role")

    if not membership.is_active:
        membership.is_active = True
        update_fields.append("is_active")

    if is_primary and not membership.is_primary:
        TeamMembership.objects.filter(
            user=user,
            is_primary=True,
            is_active=True,
        ).exclude(pk=membership.pk).update(is_primary=False)
        membership.is_primary = True
        update_fields.append("is_primary")

    if update_fields:
        membership.save(update_fields=update_fields)

    sync_user_profile_team_from_memberships(user)
    _ensure_member_organization_role(user)
    return membership


@transaction.atomic
def remove_team_membership(
    user: User,  # type: ignore[type-arg]
    team: Team,
    *,
    role: str | None = None,
) -> None:
    queryset = TeamMembership.objects.filter(user=user, team=team)
    if role is not None:
        queryset = queryset.filter(role=role)
    queryset.delete()
    sync_user_profile_team_from_memberships(user)
    _ensure_member_organization_role(user)


def sync_user_profile_team_from_memberships(user: User | None) -> None:  # type: ignore[type-arg]
    if not user:
        return

    profile = getattr(user, "profile", None)
    if not profile:
        return

    memberships = list(get_active_team_memberships_for_user(user))
    primary_membership = next(
        (membership for membership in memberships if membership.is_primary),
        memberships[0] if memberships else None,
    )

    if primary_membership and not primary_membership.is_primary:
        TeamMembership.objects.filter(
            user=user,
            is_primary=True,
            is_active=True,
        ).exclude(pk=primary_membership.pk).update(is_primary=False)
        primary_membership.is_primary = True
        primary_membership.save(update_fields=["is_primary"])

    primary_team = primary_membership.team if primary_membership else None
    update_fields: list[str] = []

    if profile.primary_team_id != getattr(primary_team, "id", None):
        profile.primary_team = primary_team
        update_fields.append("primary_team")

    if primary_team and profile.organization_id != primary_team.organization_id:
        profile.organization = primary_team.organization
        update_fields.append("organization")

    if update_fields:
        profile.save(update_fields=update_fields)


@transaction.atomic
def sync_team_manager_membership(team: Team, manager_user: User | None) -> None:  # type: ignore[type-arg]
    existing_manager_memberships = TeamMembership.objects.filter(
        team=team,
        role=TeamMembershipRole.MANAGER,
    )

    if manager_user is None:
        affected_user_ids = list(
            existing_manager_memberships.values_list("user_id", flat=True)
        )
        existing_manager_memberships.delete()
        for affected_user_id in affected_user_ids:
            affected_user = User.objects.filter(pk=affected_user_id).first()
            sync_user_profile_team_from_memberships(affected_user)
            _ensure_member_organization_role(affected_user)
        return

    affected_user_ids = list(
        existing_manager_memberships.exclude(user=manager_user).values_list(
            "user_id",
            flat=True,
        )
    )
    existing_manager_memberships.exclude(user=manager_user).delete()

    has_primary = TeamMembership.objects.filter(
        user=manager_user,
        is_primary=True,
        is_active=True,
    ).exists()

    upsert_team_membership(
        manager_user,
        team,
        TeamMembershipRole.MANAGER,
        is_primary=not has_primary,
    )

    for affected_user_id in affected_user_ids:
        affected_user = User.objects.filter(pk=affected_user_id).first()
        sync_user_profile_team_from_memberships(affected_user)
        _ensure_member_organization_role(affected_user)


@transaction.atomic
def assign_user_to_team(
    user: User,  # type: ignore[type-arg]
    team: Team,
    role: str,
    *,
    is_primary: bool = False,
) -> TeamMembership:
    if role == TeamMembershipRole.MANAGER:
        if team.manager_id != user.id:
            team.manager = user
            team.save(update_fields=["manager"])
        sync_team_manager_membership(team, user)
        membership = upsert_team_membership(
            user,
            team,
            TeamMembershipRole.MANAGER,
            is_primary=is_primary,
        )
    else:
        if team.manager_id == user.id:
            team.manager = None
            team.save(update_fields=["manager"])
            sync_team_manager_membership(team, None)

        membership = upsert_team_membership(
            user,
            team,
            role,
            is_primary=is_primary,
        )

    sync_user_profile_team_from_memberships(user)
    _ensure_member_organization_role(user)
    return membership


@transaction.atomic
def delete_team_membership(membership: TeamMembership) -> None:
    user = membership.user
    team = membership.team
    was_manager_membership = (
        membership.role == TeamMembershipRole.MANAGER and team.manager_id == user.id
    )

    membership.delete()

    if was_manager_membership:
        team.manager = None
        team.save(update_fields=["manager"])
        sync_team_manager_membership(team, None)

    sync_user_profile_team_from_memberships(user)
    _ensure_member_organization_role(user)
