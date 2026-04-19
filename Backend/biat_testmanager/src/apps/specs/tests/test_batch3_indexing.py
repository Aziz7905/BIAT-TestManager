from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.projects.models import Project
from apps.specs.models import (
    EmbeddingModel,
    Specification,
    SpecificationIndexStatus,
    SpecificationSource,
    SpecificationSourceRecord,
    SpecificationSourceRecordStatus,
    SpecificationSourceType,
)
from apps.specs.serializers import SpecificationSerializer
from apps.specs.services.embeddings import EmbeddingResult
from apps.specs.services.embedding_models import infer_embedding_provider
from apps.specs.services.indexing import synchronize_specification_index
from apps.specs.services.ingestion import parse_specification_source
from apps.specs.services.parsers.base import ParsedSourceRecord, ParsedSourceResult


class Batch3SpecificationIndexingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="spec.owner",
            password="Pass1234!",
            email="spec.owner@biat.tn",
            first_name="Spec",
            last_name="Owner",
        )
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
            organization_role=OrganizationRole.ORG_ADMIN,
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Quality",
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Digital Banking",
            created_by=self.user,
        )

    def _build_embedding_service(self):
        vector_dimensions = settings.SPEC_EMBEDDING_VECTOR_DIMENSIONS
        embedding = [0.01] * vector_dimensions
        service = MagicMock()
        service.model_name = settings.SPEC_EMBEDDING_MODEL_NAME
        service.default_batch_size = 2
        service.embed_texts.return_value = EmbeddingResult(
            embeddings=[embedding],
            model_name=settings.SPEC_EMBEDDING_MODEL_NAME,
            device="cpu",
            batch_size=1,
            normalized=settings.SPEC_EMBEDDING_NORMALIZE,
            duration_s=0.01,
            metrics={},
        )
        return service

    @patch("apps.specs.services.indexing.get_embedding_service")
    def test_synchronize_specification_index_sets_status_and_embedding_model(
        self,
        get_embedding_service_mock,
    ):
        specification = Specification.objects.create(
            project=self.project,
            title="REQ-LOGIN",
            content="Users can sign in with valid credentials.",
            source_type=SpecificationSourceType.MANUAL,
            uploaded_by=self.user,
        )
        get_embedding_service_mock.return_value = self._build_embedding_service()

        synchronize_specification_index(specification, force=True)

        specification.refresh_from_db()
        chunk = specification.chunks.get()
        embedding_model = EmbeddingModel.objects.get(name=settings.SPEC_EMBEDDING_MODEL_NAME)

        self.assertEqual(specification.index_status, SpecificationIndexStatus.INDEXED)
        self.assertEqual(specification.index_error, "")
        self.assertIsNotNone(specification.indexed_at)
        self.assertEqual(chunk.embedding_model, settings.SPEC_EMBEDDING_MODEL_NAME)
        self.assertEqual(chunk.embedding_model_config_id, embedding_model.id)
        self.assertIsNotNone(chunk.embedding_vector)
        self.assertEqual(
            embedding_model.provider,
            infer_embedding_provider(settings.SPEC_EMBEDDING_MODEL_NAME),
        )

    def test_reparse_preserves_imported_record_instead_of_replacing_it(self):
        source = SpecificationSource.objects.create(
            project=self.project,
            name="Login source",
            source_type=SpecificationSourceType.PLAIN_TEXT,
            raw_text="REQ-LOGIN\nUsers can sign in.",
            uploaded_by=self.user,
        )
        specification = Specification.objects.create(
            project=self.project,
            source=source,
            title="REQ-LOGIN",
            content="Original imported requirement.",
            source_type=SpecificationSourceType.PLAIN_TEXT,
            uploaded_by=self.user,
        )
        preserved_record = SpecificationSourceRecord.objects.create(
            source=source,
            record_index=0,
            title="REQ-LOGIN",
            content="Original curated requirement.",
            external_reference="REQ-LOGIN",
            record_metadata={"origin": "curated"},
            linked_specification=specification,
            import_status=SpecificationSourceRecordStatus.IMPORTED,
        )

        parser = MagicMock()
        parser.parse.return_value = ParsedSourceResult(
            records=[
                ParsedSourceRecord(
                    title="REQ-LOGIN updated",
                    content="Updated parser output.",
                    external_reference="REQ-LOGIN",
                    section_label="Authentication",
                    record_metadata={"origin": "parser"},
                )
            ],
            source_metadata={"parser_name": "test"},
        )

        with patch("apps.specs.services.ingestion.get_parser_for_source", return_value=parser):
            parse_specification_source(source)

        preserved_record.refresh_from_db()

        self.assertEqual(source.records.count(), 1)
        self.assertEqual(preserved_record.linked_specification_id, specification.id)
        self.assertEqual(preserved_record.title, "REQ-LOGIN")
        self.assertEqual(
            preserved_record.record_metadata["_reconciliation_status"],
            "preserved_curated_record",
        )
        self.assertEqual(
            preserved_record.record_metadata["_latest_parse_snapshot"]["title"],
            "REQ-LOGIN updated",
        )

    @patch("apps.specs.serializers.specifications.synchronize_specification_index")
    def test_specification_serializer_create_uses_explicit_indexing_service(
        self,
        synchronize_index_mock,
    ):
        request = APIRequestFactory().post("/api/specifications/")
        request.user = self.user
        serializer = SpecificationSerializer(
            data={
                "project": self.project.id,
                "title": "REQ-PASSWORD-RESET",
                "content": "Users can request a password reset link.",
                "source_type": SpecificationSourceType.MANUAL,
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        specification = serializer.save()

        synchronize_index_mock.assert_called_once_with(specification, force=True)

    @patch("apps.specs.serializers.specifications.synchronize_specification_index")
    def test_specification_serializer_update_uses_explicit_indexing_service_on_content_change(
        self,
        synchronize_index_mock,
    ):
        specification = Specification.objects.create(
            project=self.project,
            title="REQ-OTP",
            content="The platform sends OTP codes.",
            source_type=SpecificationSourceType.MANUAL,
            uploaded_by=self.user,
        )
        request = APIRequestFactory().patch("/api/specifications/")
        request.user = self.user
        serializer = SpecificationSerializer(
            instance=specification,
            data={"content": "The platform sends OTP codes by SMS."},
            partial=True,
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_specification = serializer.save()

        synchronize_index_mock.assert_called_once_with(updated_specification, force=True)
