from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import (
    Organization,
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
)
from apps.projects.models import Project, ProjectMember, ProjectMemberRole, ProjectStatus

User = get_user_model()


class ProjectWorkflowCleanupTests(APITestCase):
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
        self.member = User.objects.create_user(
            username="project.member",
            password="Pass1234!",
            email="project.member@biat.tn",
            first_name="Project",
            last_name="Member",
        )
        self.outside_member = User.objects.create_user(
            username="outside.member",
            password="Pass1234!",
            email="outside.member@biat.tn",
            first_name="Outside",
            last_name="Member",
        )

        for user in [self.manager, self.member, self.outside_member]:
            UserProfile.objects.create(
                user=user,
                organization=self.organization,
                organization_role=OrganizationRole.MEMBER,
            )

        TeamMembership.objects.create(
            user=self.manager,
            team=self.team,
            role=TeamMembershipRole.MANAGER,
            is_primary=True,
        )
        TeamMembership.objects.create(
            user=self.member,
            team=self.team,
            role=TeamMembershipRole.TESTER,
            is_primary=True,
        )
        self.client.force_authenticate(self.manager)

    def test_create_project_api_creates_owner_membership_for_team_member(self):
        response = self.client.post(
            reverse("project-list-create"),
            {
                "team": str(self.team.id),
                "name": "Payments",
                "description": "Payments regression workspace",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(name="Payments")
        owner = ProjectMember.objects.get(project=project, user=self.manager)
        self.assertEqual(owner.role, ProjectMemberRole.OWNER)

    def test_project_list_is_paginated(self):
        Project.objects.bulk_create(
            [
                Project(
                    team=self.team,
                    name=f"Project {index:03d}",
                    created_by=self.manager,
                )
                for index in range(51)
            ]
        )

        response = self.client.get(reverse("project-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 51)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 50)

    def test_archive_and_restore_project_are_explicit_workflows(self):
        project = Project.objects.create(
            team=self.team,
            name="Cards",
            created_by=self.manager,
        )

        archive_response = self.client.post(reverse("project-archive", kwargs={"pk": project.id}))
        project.refresh_from_db()

        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(project.status, ProjectStatus.ARCHIVED)

        restore_response = self.client.post(reverse("project-restore", kwargs={"pk": project.id}))
        project.refresh_from_db()

        self.assertEqual(restore_response.status_code, status.HTTP_200_OK)
        self.assertEqual(project.status, ProjectStatus.ACTIVE)

    def test_project_member_add_requires_team_membership_first(self):
        project = Project.objects.create(
            team=self.team,
            name="Core Banking",
            created_by=self.manager,
        )

        response = self.client.post(
            reverse("project-member-list-create", kwargs={"project_pk": project.id}),
            {"user": self.outside_member.id, "role": ProjectMemberRole.EDITOR},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team first", str(response.data["user"][0]))

    def test_project_member_update_and_remove_use_workflow_services(self):
        project = Project.objects.create(
            team=self.team,
            name="Mobile",
            created_by=self.manager,
        )
        membership = ProjectMember.objects.create(
            project=project,
            user=self.member,
            role=ProjectMemberRole.VIEWER,
        )

        update_response = self.client.patch(
            reverse(
                "project-member-detail",
                kwargs={"project_pk": project.id, "membership_pk": membership.id},
            ),
            {"role": ProjectMemberRole.EDITOR},
            format="json",
        )
        membership.refresh_from_db()

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(membership.role, ProjectMemberRole.EDITOR)

        delete_response = self.client.delete(
            reverse(
                "project-member-detail",
                kwargs={"project_pk": project.id, "membership_pk": membership.id},
            )
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProjectMember.objects.filter(id=membership.id).exists())
