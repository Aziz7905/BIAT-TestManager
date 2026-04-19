#src/app/projects/services.py

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import Team, TeamMembership
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.projects.models.project import ProjectStatus

User = get_user_model()


@transaction.atomic
def create_project_for_team(
    *,
    team: Team,
    name: str,
    created_by: User | None = None,  # type: ignore[type-arg]
    description: str = "",
    status: str = ProjectStatus.ACTIVE,
) -> Project:
    """Create a project and make the creator an owner when they belong to the team."""
    project = Project.objects.create(
        team=team,
        name=name,
        description=description,
        status=status,
        created_by=created_by,
    )

    if created_by and TeamMembership.objects.filter(
        user=created_by,
        team=team,
        is_active=True,
    ).exists():
        ProjectMember.objects.update_or_create(
            project=project,
            user=created_by,
            defaults={"role": ProjectMemberRole.OWNER},
        )

    return project


@transaction.atomic
def update_project_details(project: Project, **changes) -> Project:
    """Update editable project fields through the project workflow."""
    update_fields: list[str] = []
    for field_name in ["team", "name", "description", "status"]:
        if field_name in changes:
            setattr(project, field_name, changes[field_name])
            update_fields.append(field_name)

    if update_fields:
        project.save(update_fields=[*update_fields, "updated_at"])
    return project


def archive_project(project: Project) -> Project:
    """Archive a project while preserving its repository, specs, and run history."""
    return update_project_details(project, status=ProjectStatus.ARCHIVED)


def restore_project(project: Project) -> Project:
    """Restore an archived project to active work."""
    return update_project_details(project, status=ProjectStatus.ACTIVE)


@transaction.atomic
def add_project_member(
    *,
    project: Project,
    user: User,  # type: ignore[type-arg]
    role: str,
) -> ProjectMember:
    """Add a team member to a project with an explicit project role."""
    return ProjectMember.objects.create(
        project=project,
        user=user,
        role=role,
    )


@transaction.atomic
def update_project_member_role(
    membership: ProjectMember,
    *,
    role: str,
) -> ProjectMember:
    """Change a user's role inside one project."""
    if membership.role != role:
        membership.role = role
        membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def remove_project_member(membership: ProjectMember) -> None:
    """Remove a user's project-level permission."""
    membership.delete()
