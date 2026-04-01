from django.contrib.auth import get_user_model

from apps.accounts.models import Team, TeamMembership, TeamMembershipRole, UserProfileRole

User = get_user_model()


VISIBLE_TEAM_ROLES = {
    UserProfileRole.PLATFORM_OWNER,
    UserProfileRole.ORG_ADMIN,
    UserProfileRole.TEAM_MANAGER,
}

TEAM_MEMBERSHIP_PROFILE_ROLES = {
    UserProfileRole.TEAM_MANAGER,
    UserProfileRole.TESTER,
    UserProfileRole.VIEWER,
}

CREATE_USER_ROLES = {
    UserProfileRole.PLATFORM_OWNER,
    UserProfileRole.ORG_ADMIN,
}


def get_user_role(user) -> str | None:
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", None)


def is_platform_owner(user) -> bool:
    return user.is_superuser or get_user_role(user) == UserProfileRole.PLATFORM_OWNER


def is_org_admin(user) -> bool:
    return get_user_role(user) == UserProfileRole.ORG_ADMIN


def is_team_manager(user) -> bool:
    return get_user_role(user) == UserProfileRole.TEAM_MANAGER


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
    return user.is_superuser or get_user_role(user) in CREATE_USER_ROLES


def can_update_users(user) -> bool:
    return user.is_superuser or get_user_role(user) in {
        UserProfileRole.PLATFORM_OWNER,
        UserProfileRole.ORG_ADMIN,
        UserProfileRole.TEAM_MANAGER,
    }


def can_delete_users(user) -> bool:
    return can_update_users(user)


def can_view_users(user) -> bool:
    role = get_user_role(user)
    return user.is_superuser or role in {
        UserProfileRole.PLATFORM_OWNER,
        UserProfileRole.ORG_ADMIN,
        UserProfileRole.TEAM_MANAGER,
    }


def can_manage_target_user(actor, target) -> bool:
    if actor.is_superuser or is_platform_owner(actor):
        return True

    actor_profile = getattr(actor, "profile", None)
    target_profile = getattr(target, "profile", None)
    if not actor_profile or not target_profile:
        return False

    if actor_profile.role == UserProfileRole.ORG_ADMIN:
        return (
            actor_profile.organization_id == target_profile.organization_id
            and target_profile.role != UserProfileRole.PLATFORM_OWNER
        )

    if actor_profile.role == UserProfileRole.TEAM_MANAGER:
        managed_team_ids = get_managed_team_ids_for_user(actor)
        return (
            bool(managed_team_ids)
            and TeamMembership.objects.filter(
                user=target,
                team_id__in=managed_team_ids,
                is_active=True,
            ).exists()
            and target_profile.role in {
                UserProfileRole.TESTER,
                UserProfileRole.VIEWER,
            }
        )

    return False


def can_create_teams(user) -> bool:
    role = get_user_role(user)
    return user.is_superuser or role in {
        UserProfileRole.PLATFORM_OWNER,
        UserProfileRole.ORG_ADMIN,
    }


def can_view_teams(user) -> bool:
    return user.is_superuser or get_user_role(user) in VISIBLE_TEAM_ROLES


def can_manage_team_record(user, team: Team) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    if profile.role == UserProfileRole.ORG_ADMIN:
        return profile.organization_id == team.organization_id

    if profile.role == UserProfileRole.TEAM_MANAGER:
        return TeamMembership.objects.filter(
            user=user,
            team=team,
            role=TeamMembershipRole.MANAGER,
            is_active=True,
        ).exists()

    return False


def can_manage_team_api_key(user, team: Team) -> bool:
    return can_manage_team_record(user, team)


def can_add_team_members(user, team: Team) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    return (
        profile.role == UserProfileRole.ORG_ADMIN
        and profile.organization_id == team.organization_id
    )


def can_view_team_members(user, team: Team) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    if profile.role == UserProfileRole.ORG_ADMIN:
        return profile.organization_id == team.organization_id

    if profile.role == UserProfileRole.TEAM_MANAGER:
        return TeamMembership.objects.filter(
            user=user,
            team=team,
            role=TeamMembershipRole.MANAGER,
            is_active=True,
        ).exists()

    return False


def can_manage_team_membership_record(actor, membership: TeamMembership) -> bool:
    target = membership.user
    target_profile = getattr(target, "profile", None)

    if not target_profile or target_profile.role not in TEAM_MEMBERSHIP_PROFILE_ROLES:
        return False

    if actor.is_superuser or is_platform_owner(actor):
        return True

    actor_profile = getattr(actor, "profile", None)
    if not actor_profile:
        return False

    if actor_profile.role == UserProfileRole.ORG_ADMIN:
        return (
            actor_profile.organization_id == membership.team.organization_id
            and target_profile.role != UserProfileRole.PLATFORM_OWNER
        )

    if actor_profile.role == UserProfileRole.TEAM_MANAGER:
        return (
            membership.role in {
                TeamMembershipRole.TESTER,
                TeamMembershipRole.VIEWER,
            }
            and target_profile.role in {
                UserProfileRole.TESTER,
                UserProfileRole.VIEWER,
            }
            and TeamMembership.objects.filter(
                user=actor,
                team=membership.team,
                role=TeamMembershipRole.MANAGER,
                is_active=True,
            ).exists()
        )

    return False


def get_user_queryset_for_actor(actor):
    queryset = User.objects.select_related(
        "profile",
        "profile__organization",
        "profile__team",
    ).prefetch_related(
        "team_memberships__team",
    ).order_by("-date_joined")

    role = get_user_role(actor)

    if actor.is_superuser or role == UserProfileRole.PLATFORM_OWNER:
        return queryset

    if role == UserProfileRole.ORG_ADMIN:
        return queryset.filter(
            profile__organization_id=actor.profile.organization_id
        ).exclude(profile__role=UserProfileRole.PLATFORM_OWNER)

    if role == UserProfileRole.TEAM_MANAGER:
        managed_team_ids = get_managed_team_ids_for_user(actor)
        if not managed_team_ids:
            return queryset.none()
        return queryset.filter(
            team_memberships__team_id__in=managed_team_ids,
            team_memberships__is_active=True,
        ).exclude(
            profile__role__in=[
                UserProfileRole.PLATFORM_OWNER,
                UserProfileRole.ORG_ADMIN,
            ]
        ).distinct()

    return queryset.none()


def get_team_queryset_for_actor(actor):
    queryset = Team.objects.select_related(
        "organization",
        "manager",
        "ai_provider",
    ).prefetch_related(
        "memberships__user",
    ).order_by("name")

    role = get_user_role(actor)

    if actor.is_superuser or role == UserProfileRole.PLATFORM_OWNER:
        return queryset

    if role == UserProfileRole.ORG_ADMIN:
        return queryset.filter(organization_id=actor.profile.organization_id)

    if role == UserProfileRole.TEAM_MANAGER:
        return queryset.filter(
            memberships__user=actor,
            memberships__role=TeamMembershipRole.MANAGER,
            memberships__is_active=True,
        ).distinct()

    return queryset.none()
