from django.db import migrations, models


def _map_legacy_role_to_organization_role(legacy_role: str | None) -> str:
    if legacy_role == "platform_owner":
        return "platform_owner"
    if legacy_role == "org_admin":
        return "org_admin"
    return "member"


def _map_legacy_role_to_membership_role(legacy_role: str | None) -> str | None:
    if legacy_role == "team_manager":
        return "manager"
    if legacy_role == "tester":
        return "tester"
    if legacy_role == "viewer":
        return "viewer"
    return None


def _map_membership_role_to_legacy_role(membership_role: str | None) -> str:
    if membership_role == "manager":
        return "team_manager"
    if membership_role == "tester":
        return "tester"
    if membership_role == "viewer":
        return "viewer"
    return "viewer"


def _set_primary_membership(TeamMembership, user_id, membership):
    TeamMembership.objects.filter(
        user_id=user_id,
        is_primary=True,
        is_active=True,
    ).exclude(pk=membership.pk).update(is_primary=False)

    if not membership.is_primary:
        membership.is_primary = True
        membership.save(update_fields=["is_primary"])


def _ensure_membership(
    TeamMembership,
    *,
    user_id,
    team_id,
    role,
    is_primary,
):
    membership, _ = TeamMembership.objects.get_or_create(
        user_id=user_id,
        team_id=team_id,
        defaults={
            "role": role,
            "is_primary": is_primary,
            "is_active": True,
        },
    )

    update_fields = []
    if role and membership.role != role:
        membership.role = role
        update_fields.append("role")

    if not membership.is_active:
        membership.is_active = True
        update_fields.append("is_active")

    if update_fields:
        membership.save(update_fields=update_fields)

    if is_primary:
        _set_primary_membership(TeamMembership, user_id, membership)

    return membership


def forwards(apps, schema_editor):
    Team = apps.get_model("accounts", "Team")
    TeamMembership = apps.get_model("accounts", "TeamMembership")
    UserProfile = apps.get_model("accounts", "UserProfile")

    for profile in UserProfile.objects.all().iterator():
        legacy_role = profile.organization_role
        membership_role = _map_legacy_role_to_membership_role(legacy_role)

        if profile.primary_team_id and membership_role:
            _ensure_membership(
                TeamMembership,
                user_id=profile.user_id,
                team_id=profile.primary_team_id,
                role=membership_role,
                is_primary=True,
            )

        profile.organization_role = _map_legacy_role_to_organization_role(legacy_role)
        profile.save(update_fields=["organization_role"])

    for team in Team.objects.exclude(manager_id__isnull=True).iterator():
        membership = _ensure_membership(
            TeamMembership,
            user_id=team.manager_id,
            team_id=team.id,
            role="manager",
            is_primary=False,
        )

        has_primary = TeamMembership.objects.filter(
            user_id=team.manager_id,
            is_primary=True,
            is_active=True,
        ).exists()
        if not has_primary:
            _set_primary_membership(TeamMembership, team.manager_id, membership)


def backwards(apps, schema_editor):
    TeamMembership = apps.get_model("accounts", "TeamMembership")
    UserProfile = apps.get_model("accounts", "UserProfile")

    for profile in UserProfile.objects.all().iterator():
        if profile.organization_role in {"platform_owner", "org_admin"}:
            continue

        memberships = list(
            TeamMembership.objects.filter(
                user_id=profile.user_id,
                is_active=True,
            ).order_by("-is_primary", "joined_at")
        )
        membership = next(
            (item for item in memberships if item.is_primary),
            memberships[0] if memberships else None,
        )
        profile.organization_role = _map_membership_role_to_legacy_role(
            getattr(membership, "role", None)
        )
        profile.save(update_fields=["organization_role"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_teammembership"),
    ]

    operations = [
        migrations.RenameField(
            model_name="userprofile",
            old_name="team",
            new_name="primary_team",
        ),
        migrations.RenameField(
            model_name="userprofile",
            old_name="role",
            new_name="organization_role",
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="organization_role",
            field=models.CharField(
                choices=[
                    ("platform_owner", "Platform Owner"),
                    ("org_admin", "Org Admin"),
                    ("member", "Member"),
                ],
                default="member",
                max_length=30,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
