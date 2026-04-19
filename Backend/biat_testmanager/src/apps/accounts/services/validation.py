from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Organization, OrganizationRole, Team, build_org_email

User = get_user_model()


def validate_team_belongs_to_organization(team: Team | None, organization: Organization | None) -> None:
    if team and organization and team.organization_id != organization.id:
        raise serializers.ValidationError(
            {"team": "Team must belong to the same organization."}
        )


def validate_manager_for_organization(manager_user, organization: Organization | None) -> None:
    if not manager_user:
        return

    manager_profile = getattr(manager_user, "profile", None)
    if not manager_profile:
        raise serializers.ValidationError(
            {"manager": "Selected manager has no profile."}
        )

    if manager_profile.organization_role != OrganizationRole.MEMBER:
        raise serializers.ValidationError(
            {"manager": "Selected manager must be an organization member."}
        )

    if organization and manager_profile.organization_id != organization.id:
        raise serializers.ValidationError(
            {"manager": "Manager must belong to the same organization."}
        )


def validate_generated_email_is_available(
    first_name: str,
    last_name: str,
    organization: Organization,
    exclude_user_id: int | None = None,
) -> str:
    generated_email = build_org_email(first_name, last_name, organization.domain)

    queryset = User.objects.filter(email__iexact=generated_email)
    if exclude_user_id is not None:
        queryset = queryset.exclude(id=exclude_user_id)

    if queryset.exists():
        raise serializers.ValidationError(
            {"email": f"User with email {generated_email} already exists."}
        )

    return generated_email
