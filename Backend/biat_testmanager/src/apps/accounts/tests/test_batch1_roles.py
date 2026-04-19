from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.models import (
    Organization,
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
)
from apps.accounts.serializers.profiles import UserProfileSerializer
from apps.accounts.serializers.teams import TeamMembershipCreateSerializer
from apps.accounts.serializers.users import AdminCreateUserSerializer
from apps.accounts.services.access import can_manage_team_record

User = get_user_model()


class Batch1RoleTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="QA Core",
        )

    def _create_user(self, username: str, first_name: str, last_name: str) -> User:
        return User.objects.create_user(
            username=username,
            password="Pass1234!",  # NOSONAR
            email=f"{username}@biat.tn",
            first_name=first_name,
            last_name=last_name,
        )

    def test_membership_manager_is_the_team_authority_source(self):
        manager = self._create_user("team.manager", "Team", "Manager")
        UserProfile.objects.create(
            user=manager,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )

        TeamMembership.objects.create(
            user=manager,
            team=self.team,
            role=TeamMembershipRole.MANAGER,
            is_primary=True,
        )

        self.assertEqual(manager.profile.organization_role, OrganizationRole.MEMBER)
        self.assertTrue(can_manage_team_record(manager, self.team))

    def test_team_manager_field_no_longer_grants_authority_by_itself(self):
        manager = self._create_user("legacy.manager", "Legacy", "Manager")
        UserProfile.objects.create(
            user=manager,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        self.team.manager = manager
        self.team.save(update_fields=["manager"])

        self.assertFalse(can_manage_team_record(manager, self.team))

    def test_admin_create_user_maps_team_membership_role(self):
        admin_user = self._create_user("org.admin", "Org", "Admin")
        UserProfile.objects.create(
            user=admin_user,
            organization=self.organization,
            organization_role=OrganizationRole.ORG_ADMIN,
        )

        request = self.factory.post("/api/accounts/admin/users/")
        request.user = admin_user
        serializer = AdminCreateUserSerializer(
            data={
                "first_name": "Quality",
                "last_name": "Tester",
                "password": "Pass1234!",  # NOSONAR
                "team": str(self.team.id),
                "team_membership_role": TeamMembershipRole.TESTER,
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        created_user = serializer.save()

        profile = created_user.profile
        membership = TeamMembership.objects.get(user=created_user, team=self.team)
        payload = UserProfileSerializer(profile).data

        self.assertEqual(profile.organization_role, OrganizationRole.MEMBER)
        self.assertEqual(profile.primary_team, self.team)
        self.assertEqual(membership.role, TeamMembershipRole.TESTER)
        self.assertEqual(payload["organization_role"], OrganizationRole.MEMBER)

    def test_team_member_create_defaults_to_viewer_not_legacy_profile_role(self):
        admin_user = self._create_user("org.admin", "Org", "Admin")
        UserProfile.objects.create(
            user=admin_user,
            organization=self.organization,
            organization_role=OrganizationRole.ORG_ADMIN,
        )
        target_user = self._create_user("existing.manager", "Existing", "Manager")
        UserProfile.objects.create(
            user=target_user,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        TeamMembership.objects.create(
            user=target_user,
            team=self.team,
            role=TeamMembershipRole.MANAGER,
            is_primary=True,
        )
        second_team = Team.objects.create(
            organization=self.organization,
            name="Support QA",
        )
        request = self.factory.post(f"/api/accounts/teams/{second_team.id}/members/")
        request.user = admin_user

        serializer = TeamMembershipCreateSerializer(
            data={"user": target_user.id},
            context={"request": request, "team": second_team},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        membership = serializer.save()

        self.assertEqual(membership.role, TeamMembershipRole.VIEWER)
        manager_membership = TeamMembership.objects.get(
            user=target_user, team=self.team, role=TeamMembershipRole.MANAGER
        )
        self.assertEqual(manager_membership.role, TeamMembershipRole.MANAGER)
