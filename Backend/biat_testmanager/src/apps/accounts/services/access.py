from django.contrib.auth import get_user_model

from apps.accounts.models import (
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
)
from apps.accounts.services.roles import has_team_manager_role, get_organization_role

User = get_user_model()


def get_user_role(user) -> str | None:
    return get_organization_role(user)


def is_platform_owner(user) -> bool:
    return user.is_superuser or get_organization_role(user) == OrganizationRole.PLATFORM_OWNER


def is_org_admin(user) -> bool:
    return get_organization_role(user) == OrganizationRole.ORG_ADMIN


def is_team_manager(user) -> bool:
    return TeamMembership.objects.filter(
        user=user,
        role=TeamMembershipRole.MANAGER,
        is_active=True,
    ).exists()


def get_managed_team_ids_for_user(user) -> list[str]:
    return list(
        TeamMembership.objects.filter(
            user=user,
            role=TeamMembershipRole.MANAGER,
            is_active=True,
        ).values_list("team_id", flat=True)
    )


def can_manage_organizations(user) -> bool:
    return is_platform_owner(user)


def can_create_users(user) -> bool:
    return user.is_superuser or get_organization_role(user) in {
        OrganizationRole.PLATFORM_OWNER,
        OrganizationRole.ORG_ADMIN,
    }


def can_update_users(user) -> bool:
    return (
        user.is_superuser
        or get_organization_role(user)
        in {
            OrganizationRole.PLATFORM_OWNER,
            OrganizationRole.ORG_ADMIN,
        }
        or is_team_manager(user)
    )


def can_delete_users(user) -> bool:
    return can_update_users(user)


def can_view_users(user) -> bool:
    return can_update_users(user)


def can_manage_target_user(actor, target) -> bool:
    if actor.is_superuser or is_platform_owner(actor):
        return True

    actor_profile = getattr(actor, "profile", None)
    target_profile = getattr(target, "profile", None)
    if not actor_profile or not target_profile:
        return False

    if actor_profile.organization_role == OrganizationRole.ORG_ADMIN:
        return (
            actor_profile.organization_id == target_profile.organization_id
            and target_profile.organization_role != OrganizationRole.PLATFORM_OWNER
        )

    managed_team_ids = get_managed_team_ids_for_user(actor)
    if not managed_team_ids:
        return False

    return (
        target_profile.organization_role == OrganizationRole.MEMBER
        and TeamMembership.objects.filter(
            user=target,
            team_id__in=managed_team_ids,
            is_active=True,
        ).exists()
    )


def can_create_teams(user) -> bool:
    organization_role = get_organization_role(user)
    return user.is_superuser or organization_role in {
        OrganizationRole.PLATFORM_OWNER,
        OrganizationRole.ORG_ADMIN,
    }


def can_view_teams(user) -> bool:
    return (
        user.is_superuser
        or get_organization_role(user)
        in {
            OrganizationRole.PLATFORM_OWNER,
            OrganizationRole.ORG_ADMIN,
        }
        or is_team_manager(user)
    )


def can_manage_team_record(user, team: Team) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    if profile.organization_role == OrganizationRole.ORG_ADMIN:
        return profile.organization_id == team.organization_id

    return TeamMembership.objects.filter(
        user=user,
        team=team,
        role=TeamMembershipRole.MANAGER,
        is_active=True,
    ).exists()


def can_manage_team_api_key(user, team: Team) -> bool:
    return can_manage_team_record(user, team)


def can_add_team_members(user, team: Team) -> bool:
    return can_manage_team_record(user, team)


def can_view_team_members(user, team: Team) -> bool:
    if can_manage_team_record(user, team):
        return True

    return TeamMembership.objects.filter(
        user=user,
        team=team,
        is_active=True,
    ).exists()


def can_manage_team_membership_record(actor, membership: TeamMembership) -> bool:
    target_profile = getattr(membership.user, "profile", None)
    if not target_profile or target_profile.organization_role != OrganizationRole.MEMBER:
        return False

    if actor.is_superuser or is_platform_owner(actor):
        return True

    actor_profile = getattr(actor, "profile", None)
    if not actor_profile:
        return False

    if actor_profile.organization_role == OrganizationRole.ORG_ADMIN:
        return actor_profile.organization_id == membership.team.organization_id

    return (
        membership.role in {
            TeamMembershipRole.TESTER,
            TeamMembershipRole.VIEWER,
        }
        and TeamMembership.objects.filter(
            user=actor,
            team=membership.team,
            role=TeamMembershipRole.MANAGER,
            is_active=True,
        ).exists()
    )


def get_user_queryset_for_actor(actor):
    queryset = User.objects.select_related(
        "profile",
        "profile__organization",
        "profile__primary_team",
    ).prefetch_related("team_memberships__team").order_by("-date_joined")

    organization_role = get_organization_role(actor)

    if actor.is_superuser or organization_role == OrganizationRole.PLATFORM_OWNER:
        return queryset

    if organization_role == OrganizationRole.ORG_ADMIN:
        return queryset.filter(
            profile__organization_id=actor.profile.organization_id
        ).exclude(
            profile__organization_role=OrganizationRole.PLATFORM_OWNER
        )

    managed_team_ids = get_managed_team_ids_for_user(actor)
    if not managed_team_ids:
        return queryset.none()

    return queryset.filter(
        team_memberships__team_id__in=managed_team_ids,
        team_memberships__is_active=True,
    ).exclude(
        profile__organization_role__in=[
            OrganizationRole.PLATFORM_OWNER,
            OrganizationRole.ORG_ADMIN,
        ]
    ).distinct()


def get_team_queryset_for_actor(actor):
    queryset = Team.objects.select_related(
        "organization",
        "manager",
        "ai_config",
        "ai_config__provider",
        "ai_config__default_model_profile",
    ).prefetch_related(
        "memberships__user",
        "integration_configs",
    ).order_by("name")

    organization_role = get_organization_role(actor)

    if actor.is_superuser or organization_role == OrganizationRole.PLATFORM_OWNER:
        return queryset

    if organization_role == OrganizationRole.ORG_ADMIN:
        return queryset.filter(organization_id=actor.profile.organization_id)

    if has_team_manager_role(actor):
        return queryset.filter(
            memberships__user=actor,
            memberships__role=TeamMembershipRole.MANAGER,
            memberships__is_active=True,
        ).distinct()

    return queryset.none()
