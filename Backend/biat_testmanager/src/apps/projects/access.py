from django.db.models import Count

from apps.accounts.models import OrganizationRole, TeamMembership, TeamMembershipRole
from apps.accounts.services.access import get_managed_team_ids_for_user
from apps.accounts.services.roles import get_organization_role
from apps.projects.models import Project, ProjectMember


def get_user_role(user) -> str | None:
    return get_organization_role(user)


def is_platform_owner(user) -> bool:
    return user.is_superuser or get_user_role(user) == OrganizationRole.PLATFORM_OWNER


def can_create_projects(user) -> bool:
    return user.is_superuser or get_user_role(user) in {
        OrganizationRole.PLATFORM_OWNER,
        OrganizationRole.ORG_ADMIN,
    } or TeamMembership.objects.filter(
        user=user,
        role=TeamMembershipRole.MANAGER,
        is_active=True,
    ).exists()


def can_view_projects(user) -> bool:
    return user.is_authenticated


def can_manage_project_record(user, project: Project) -> bool:
    if user.is_superuser or is_platform_owner(user):
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False

    if profile.organization_role == OrganizationRole.ORG_ADMIN:
        return profile.organization_id == project.team.organization_id

    return TeamMembership.objects.filter(
        user=user,
        team=project.team,
        role=TeamMembershipRole.MANAGER,
        is_active=True,
    ).exists()


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
    ).annotate(
        member_count_value=Count("members", distinct=True),
    ).order_by("name")

    organization_role = get_user_role(actor)

    if actor.is_superuser or organization_role == OrganizationRole.PLATFORM_OWNER:
        return queryset

    if organization_role == OrganizationRole.ORG_ADMIN:
        return queryset.filter(team__organization_id=actor.profile.organization_id)

    managed_team_ids = get_managed_team_ids_for_user(actor)
    if managed_team_ids:
        return queryset.filter(team_id__in=managed_team_ids).distinct()

    return queryset.filter(members__user=actor).distinct()
