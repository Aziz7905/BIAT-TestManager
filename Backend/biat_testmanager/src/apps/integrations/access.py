from apps.accounts.services.access import can_manage_team_record
from apps.projects.access import can_manage_project_record, get_project_queryset_for_actor
from apps.projects.models import Project, ProjectMember, ProjectMemberRole


def can_view_project_integrations(user, project: Project) -> bool:
    if not user.is_authenticated:
        return False
    return get_project_queryset_for_actor(user).filter(pk=project.pk).exists()


def can_manage_project_integrations(user, project: Project) -> bool:
    if can_manage_project_record(user, project):
        return True

    return ProjectMember.objects.filter(
        project=project,
        user=user,
        role__in=[ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR],
    ).exists()


def can_manage_team_integrations(user, team) -> bool:
    return can_manage_team_record(user, team)
