from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase as DjangoTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus, AIGenerationSourceType
from apps.ai.providers.base import ChatResponse
from apps.ai.services.capacity import AICapacityExceededError
from apps.ai.services.commit_service import commit_selected_drafts
from apps.ai.services.context_retrieval import retrieve_generation_context
from apps.ai.services.generation_session import start_generation_session
from apps.ai.services.test_generation_workflow import run_test_generation_workflow
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import SpecChunk, SpecChunkType, Specification, SpecificationSourceType
from apps.testing.models import TestCase as RepositoryTestCase
from apps.testing.models import TestCaseDesignStatus, TestPriority
from apps.testing.services import (
    create_test_case_with_revision,
    create_test_scenario,
    create_test_suite,
    get_or_create_default_section,
)

User = get_user_model()


class FakeProvider:
    name = "groq"
    model_name = "llama-3.3-70b-versatile"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **opts):
        self.calls.append({"messages": messages, "opts": opts})
        payload = self.responses.pop(0)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return ChatResponse(
            content=content,
            input_tokens=11,
            output_tokens=17,
            finish_reason="stop",
            raw={},
        )


def make_user(username, organization, role=OrganizationRole.MEMBER):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@biat.tn",
        password="Pass1234!",
    )
    UserProfile.objects.create(
        user=user,
        organization=organization,
        organization_role=role,
    )
    return user


def make_valid_draft(case_ids=None):
    case_ids = case_ids or ["case-valid-login", "case-invalid-login"]
    return {
        "summary": "Authentication login coverage.",
        "assumptions": [],
        "open_questions": [],
        "suite": {
            "draft_id": "suite-auth",
            "name": "Authentication",
            "description": "Authentication tests.",
        },
        "sections": [
            {
                "draft_id": "section-login",
                "name": "Login",
                "scenarios": [
                    {
                        "draft_id": "scenario-login",
                        "title": "Login authentication",
                        "description": "Validate login behavior.",
                        "scenario_type": "happy_path",
                        "priority": "high",
                        "business_priority": "must_have",
                        "polarity": "positive",
                        "confidence": 0.91,
                        "cases": [
                            {
                                "draft_id": case_ids[0],
                                "title": "Login with valid credentials",
                                "preconditions": "User is on the login page.",
                                "steps": [
                                    {
                                        "step_index": 0,
                                        "action": "Enter valid username and password.",
                                        "expected_outcome": "Credentials are accepted.",
                                    },
                                    {
                                        "step_index": 1,
                                        "action": "Submit the login form.",
                                        "expected_outcome": "Dashboard is displayed.",
                                    },
                                ],
                                "expected_result": "Dashboard is displayed.",
                                "test_data": {"username": "valid.user"},
                                "linked_spec_ids": [],
                            },
                            {
                                "draft_id": case_ids[1],
                                "title": "Login with invalid password",
                                "preconditions": "User is on the login page.",
                                "steps": [
                                    {
                                        "step_index": 0,
                                        "action": "Enter a valid username and wrong password.",
                                        "expected_outcome": "The form remains visible.",
                                    }
                                ],
                                "expected_result": "An invalid credentials error is displayed.",
                                "test_data": {"username": "valid.user"},
                                "linked_spec_ids": [],
                            },
                        ],
                    }
                ],
            }
        ],
    }


def make_critic_response(draft):
    return {
        "critic_report": {
            "quality_score": 0.88,
            "duplicates": [],
            "missing_coverage": [],
        },
        "draft_payload": draft,
    }


def make_nested_section_draft():
    draft = make_valid_draft(case_ids=["case-online-valid", "case-online-invalid"])
    root_section = draft["sections"][0]
    login_scenario = root_section["scenarios"][0]
    root_section["scenarios"] = []
    root_section["children"] = [
        {
            "draft_id": "section-login-online",
            "name": "Online login",
            "scenarios": [
                login_scenario,
            ],
        },
        {
            "draft_id": "section-login-lockout",
            "name": "Lockout",
            "scenarios": [
                {
                    "draft_id": "scenario-lockout",
                    "title": "Login lockout",
                    "description": "Validate account lockout behavior.",
                    "scenario_type": "edge_case",
                    "priority": "medium",
                    "business_priority": "should_have",
                    "polarity": "negative",
                    "confidence": 0.76,
                    "cases": [
                        {
                            "draft_id": "case-lockout",
                            "title": "Account locks after repeated invalid attempts",
                            "preconditions": "User exists and lockout policy is active.",
                            "steps": [
                                {
                                    "step_index": 0,
                                    "action": "Submit invalid credentials repeatedly.",
                                    "expected_outcome": "The account is locked.",
                                }
                            ],
                            "expected_result": "The user cannot sign in until lockout expires.",
                            "test_data": {},
                            "linked_spec_ids": [],
                        }
                    ],
                }
            ],
        },
    ]
    return draft


class AIGenerationTestBase(DjangoTestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="BIAT AI", domain="ai.biat.tn")
        self.owner = make_user("ai.owner", self.organization, OrganizationRole.ORG_ADMIN)
        self.viewer = make_user("ai.viewer", self.organization)
        self.outsider_org = Organization.objects.create(name="Outside", domain="outside.tn")
        self.outsider = make_user("ai.outsider", self.outsider_org)
        self.team = Team.objects.create(organization=self.organization, name="AI QA")
        self.project = Project.objects.create(
            team=self.team,
            name="Digital Banking",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMemberRole.OWNER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMemberRole.VIEWER,
        )

    def make_session(self, **overrides):
        defaults = {
            "team": self.team,
            "project": self.project,
            "created_by": self.owner,
            "status": AIGenerationSessionStatus.QUEUED,
            "source_type": AIGenerationSourceType.PROMPT,
            "objective": "Generate login authentication tests.",
        }
        defaults.update(overrides)
        return AIGenerationSession.objects.create(**defaults)


class AIGenerationApiAccessTests(AIGenerationTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_start_generation_without_provider_returns_clear_failure(self):
        response = self.client.post(
            reverse("ai-generation-list-create"),
            {
                "project": str(self.project.id),
                "objective": "Generate login tests.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("AI", str(response.data))

    def test_user_without_project_access_cannot_view_session(self):
        session = self.make_session(status=AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.client.force_authenticate(self.outsider)

        response = self.client.get(reverse("ai-generation-detail", kwargs={"pk": session.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(AI_MAX_CONCURRENT_GENERATION_SESSIONS_PER_TEAM=1)
    def test_start_generation_rejects_team_over_capacity(self):
        self.make_session(status=AIGenerationSessionStatus.GENERATING)

        with self.assertRaises(AICapacityExceededError):
            start_generation_session(
                user=self.owner,
                project=self.project,
                objective="Generate login tests.",
                source_type=AIGenerationSourceType.PROMPT,
            )


class AIGenerationWorkflowTests(AIGenerationTestBase):
    def test_prompt_only_generation_with_mocked_llm_reaches_review(self):
        existing_suite = create_test_suite(self.project, name="Existing Authentication", created_by=self.owner)
        existing_section = get_or_create_default_section(existing_suite)
        existing_scenario = create_test_scenario(
            existing_section,
            title="Existing valid login",
            description="Existing login coverage.",
            priority=TestPriority.HIGH,
        )
        create_test_case_with_revision(
            scenario=existing_scenario,
            title="Existing valid login case",
            preconditions="User is on login page.",
            steps=[{"step_index": 0, "action": "Log in", "expected_outcome": "Dashboard opens"}],
            expected_result="Dashboard opens.",
            test_data={},
            design_status=TestCaseDesignStatus.APPROVED,
            automation_status="manual",
        )
        draft = make_valid_draft()
        fake_provider = FakeProvider([draft, make_critic_response(draft)])
        session = self.make_session()

        with patch(
            "apps.ai.services.test_generation_workflow.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.services.test_generation_workflow.retrieve_generation_context",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertEqual(session.provider_name, "groq")
        self.assertEqual(session.model_name, "llama-3.3-70b-versatile")
        self.assertEqual(session.input_tokens, 22)
        self.assertEqual(session.output_tokens, 34)
        self.assertTrue(session.draft_payload["possible_duplicates"])

    def test_generation_with_spec_context_stores_retrieved_context_rows(self):
        specification = Specification.objects.create(
            project=self.project,
            title="REQ-LOGIN",
            content="Users must be able to sign in with valid credentials.",
            source_type=SpecificationSourceType.MANUAL,
            uploaded_by=self.owner,
        )
        chunk = SpecChunk.objects.create(
            specification=specification,
            chunk_index=0,
            chunk_type=SpecChunkType.FUNCTIONAL_REQUIREMENT,
            content="Login must accept valid credentials and reject invalid passwords.",
        )
        session = self.make_session(attached_specification=specification)

        with patch(
            "apps.ai.services.context_retrieval.retrieve_similar_chunks",
            side_effect=RuntimeError("vector search unavailable"),
        ):
            context = retrieve_generation_context(session, top_k=5)

        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["chunk_id"], str(chunk.id))
        stored_context = session.retrieved_contexts.get()
        self.assertEqual(stored_context.object_id, str(chunk.id))

    def test_invalid_draft_json_is_repaired_once(self):
        repaired = make_valid_draft()
        fake_provider = FakeProvider(
            [
                "not a json object",
                repaired,
                make_critic_response(repaired),
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.services.test_generation_workflow.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.services.test_generation_workflow.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.services.test_generation_workflow.search_repository_memory",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertEqual(len(fake_provider.calls), 3)
        self.assertEqual(session.draft_payload["suite"]["name"], "Authentication")

    def test_invalid_repair_fails_session_clearly(self):
        fake_provider = FakeProvider(
            [
                {"summary": "Missing suite and sections."},
                {"summary": "Still invalid."},
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.services.test_generation_workflow.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.services.test_generation_workflow.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.services.test_generation_workflow.search_repository_memory",
            return_value=[],
        ):
            with self.assertRaises(Exception):
                run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.FAILED)
        self.assertTrue(session.error_message)


class AIGenerationCommitTests(AIGenerationTestBase):
    def test_commit_selected_draft_creates_canonical_rows_only_for_selected_cases(self):
        specification = Specification.objects.create(
            project=self.project,
            title="REQ-AUTH",
            content="Authentication requirements.",
            source_type=SpecificationSourceType.MANUAL,
            uploaded_by=self.owner,
        )
        draft = make_valid_draft()
        draft["sections"][0]["scenarios"][0]["cases"][0]["linked_spec_ids"] = [
            str(specification.id)
        ]
        session = self.make_session(
            status=AIGenerationSessionStatus.REVIEWING,
            draft_payload=draft,
            review_decisions={
                "draft_payload": draft,
                "selected_case_ids": ["case-valid-login"],
            },
            attached_specification=specification,
        )

        summary = commit_selected_drafts(session=session)

        self.assertEqual(summary["created_case_count"], 1)
        self.assertEqual(RepositoryTestCase.objects.count(), 1)
        test_case = RepositoryTestCase.objects.get()
        self.assertEqual(test_case.title, "Login with valid credentials")
        self.assertNotEqual(test_case.title, "Login with invalid password")
        self.assertTrue(test_case.ai_generated)
        self.assertTrue(test_case.scenario.ai_generated)
        self.assertTrue(test_case.scenario.section.suite.ai_generated)
        self.assertEqual(test_case.design_status, TestCaseDesignStatus.DRAFT)
        self.assertEqual(test_case.revisions.count(), 1)
        self.assertSetEqual(
            set(test_case.linked_specifications.values_list("id", flat=True)),
            {specification.id},
        )
        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.SAVED)

    def test_commit_save_and_approve_sets_approved_design_status(self):
        draft = make_valid_draft(case_ids=["case-approved", "case-dropped"])
        session = self.make_session(
            status=AIGenerationSessionStatus.REVIEWING,
            draft_payload=draft,
            review_decisions={
                "draft_payload": draft,
                "selected_case_ids": ["case-approved"],
            },
        )

        commit_selected_drafts(session=session, create_as_approved=True)

        test_case = RepositoryTestCase.objects.get()
        self.assertEqual(test_case.design_status, TestCaseDesignStatus.APPROVED)

    def test_commit_nested_sections_follows_repository_tree(self):
        draft = make_nested_section_draft()
        session = self.make_session(
            status=AIGenerationSessionStatus.REVIEWING,
            draft_payload=draft,
            review_decisions={
                "draft_payload": draft,
                "selected_case_ids": ["case-online-valid", "case-lockout"],
            },
        )

        summary = commit_selected_drafts(session=session)

        self.assertEqual(summary["created_case_count"], 2)
        suite = session.project.test_suites.get(name="Authentication")
        root = suite.sections.get(name="Login", parent__isnull=True)
        online = suite.sections.get(name="Online login", parent=root)
        lockout = suite.sections.get(name="Lockout", parent=root)
        self.assertEqual(root.scenarios.count(), 0)
        self.assertEqual(online.scenarios.count(), 1)
        self.assertEqual(lockout.scenarios.count(), 1)
        self.assertEqual(
            set(RepositoryTestCase.objects.values_list("title", flat=True)),
            {
                "Login with valid credentials",
                "Account locks after repeated invalid attempts",
            },
        )
