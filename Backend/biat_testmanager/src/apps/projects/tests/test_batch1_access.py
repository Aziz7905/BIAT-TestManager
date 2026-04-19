from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import (
    Organization,
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
)
from apps.projects.access import can_create_projects, can_manage_project_record
from apps.projects.models import Project

User = get_user_model()


class Batch1ProjectAccessTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Delivery",
        )
        self.manager = User.objects.create_user(
            username="manager.user",
            password="Pass1234!",
            email="manager.user@biat.tn",
            first_name="Manager",
            last_name="User",
        )
        UserProfile.objects.create(
            user=self.manager,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        TeamMembership.objects.create(
            user=self.manager,
            team=self.team,
            role=TeamMembershipRole.MANAGER,
            is_primary=True,
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Payments",
            created_by=self.manager,
        )

    def test_team_manager_membership_can_create_and_manage_projects(self):
        self.assertTrue(can_create_projects(self.manager))
        self.assertTrue(can_manage_project_record(self.manager, self.project))
