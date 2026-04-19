from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, OrganizationRole, Team, UserProfile
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import (
    Specification,
    SpecificationSource,
    SpecificationSourceParserStatus,
    SpecificationSourceRecord,
    SpecificationSourceType,
)


class SpecificationNonAICleanupRegressionTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.organization = Organization.objects.create(
            name="BIAT IT",
            domain="biat-it.tn",
        )
        self.user = user_model.objects.create_user(
            username="spec.owner",
            password="Pass1234!",
            email="spec.owner@biat-it.tn",
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Quality",
            manager=self.user,
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Digital Banking",
            created_by=self.user,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMemberRole.OWNER,
        )
        self.client.force_authenticate(self.user)

    def test_specification_list_is_paginated(self):
        specifications = [
            Specification(
                project=self.project,
                title=f"REQ-{index:03d}",
                content=f"Requirement {index}",
                source_type=SpecificationSourceType.MANUAL,
                uploaded_by=self.user,
            )
            for index in range(51)
        ]
        Specification.objects.bulk_create(specifications)

        response = self.client.get(reverse("specification-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 51)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 50)

    @patch("apps.specs.services.ingestion.synchronize_specification_index")
    def test_selected_source_record_import_still_creates_specification(self, index_mock):
        source = SpecificationSource.objects.create(
            project=self.project,
            name="Login source",
            source_type=SpecificationSourceType.PLAIN_TEXT,
            raw_text="REQ-LOGIN\nUsers can sign in.",
            parser_status=SpecificationSourceParserStatus.READY,
            uploaded_by=self.user,
        )
        record = SpecificationSourceRecord.objects.create(
            source=source,
            record_index=0,
            title="REQ-LOGIN",
            content="Users can sign in.",
            external_reference="REQ-LOGIN",
            is_selected=True,
        )

        response = self.client.post(
            reverse("specification-source-import", kwargs={"pk": source.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["imported_count"], 1)
        record.refresh_from_db()
        self.assertIsNotNone(record.linked_specification_id)
        self.assertEqual(
            Specification.objects.get(id=record.linked_specification_id).title,
            "REQ-LOGIN",
        )
        index_mock.assert_called_once()

    def test_delete_selected_source_records_removes_only_checked_rows(self):
        source = SpecificationSource.objects.create(
            project=self.project,
            name="Login source",
            source_type=SpecificationSourceType.PLAIN_TEXT,
            raw_text="REQ-LOGIN\nUsers can sign in.",
            parser_status=SpecificationSourceParserStatus.READY,
            uploaded_by=self.user,
        )
        selected_record = SpecificationSourceRecord.objects.create(
            source=source,
            record_index=0,
            title="REQ-LOGIN",
            content="Users can sign in.",
            external_reference="REQ-LOGIN",
            is_selected=True,
        )
        SpecificationSourceRecord.objects.create(
            source=source,
            record_index=1,
            title="REQ-RESET",
            content="Users can reset password.",
            external_reference="REQ-RESET",
            is_selected=False,
        )

        response = self.client.delete(
            reverse("specification-source-record-selected-delete", kwargs={"source_pk": source.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted_count"], 1)
        self.assertFalse(
            SpecificationSourceRecord.objects.filter(id=selected_record.id).exists()
        )
        self.assertTrue(
            SpecificationSourceRecord.objects.filter(
                source=source,
                external_reference="REQ-RESET",
            ).exists()
        )
