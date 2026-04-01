from apps.accounts.models import TeamMembership, TeamMembershipRole, UserProfileRole
from apps.accounts.services.access import get_managed_team_ids_for_user
from apps.projects.models import Project, ProjectMember


def get_user_role(user) -> str | None:
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", None)


def is_platform_owner(user) -> bool:
    return user.is_superuser or get_user_role(user) == UserProfileRole.PLATFORM_OWNER


def can_create_projects(user) -> bool:
    return user.is_superuser or get_user_role(user) in {
        UserProfileRole.PLATFORM_OWNER,
        UserProfileRole.ORG_ADMIN,
        UserProfileRole.TEAM_MANAGER,
    }


def can_view_projects(user) -> bool:
    return user.is_authenticated


def can_manage_project_record(user, project: Project) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    if profile.role == UserProfileRole.ORG_ADMIN:
        return profile.organization_id == project.team.organization_id

    if profile.role == UserProfileRole.TEAM_MANAGER:
        return TeamMembership.objects.filter(
            user=user,
            team=project.team,
            role=TeamMembershipRole.MANAGER,
            is_active=True,
        ).exists()

    return False


def can_view_project_members(user, project: Project) -> bool:
    if can_manage_project_record(user, project):
        return True

    return ProjectMember.objects.filter(project=project, user=user).exists()


def can_manage_project_member_record(user, membership: ProjectMember) -> bool:
    return can_manage_project_record(user, membership.project)


def get_project_queryset_for_actor(actor):
    queryset = Project.objects.select_related(
        "team",
        "team__organization",
        "created_by",
    ).prefetch_related(
        "members__user",
        "members__user__profile",
    ).order_by("name")

    role = get_user_role(actor)

    if actor.is_superuser or role == UserProfileRole.PLATFORM_OWNER:
        return queryset

    if role == UserProfileRole.ORG_ADMIN:
        return queryset.filter(team__organization_id=actor.profile.organization_id)

    if role == UserProfileRole.TEAM_MANAGER:
        managed_team_ids = get_managed_team_ids_for_user(actor)
        if not managed_team_ids:
            return queryset.none()
        return queryset.filter(team_id__in=managed_team_ids).distinct()

    return queryset.filter(members__user=actor).distinct()
