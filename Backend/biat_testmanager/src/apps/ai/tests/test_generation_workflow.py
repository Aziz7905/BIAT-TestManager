from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase as DjangoTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus, AIGenerationSourceType
from apps.ai.providers.base import ChatResponse, LLMProviderRequestError
from apps.ai.services.capacity import AICapacityExceededError
from apps.ai.services.sessions import start_generation_session
from apps.ai.workflows.generation.commit import commit_selected_drafts
from apps.ai.workflows.generation.contracts import generation_contract
from apps.ai.workflows.generation.context import retrieve_generation_context
from apps.ai.workflows.generation.plan import SCENARIO_EXPANSION_SCHEMA
from apps.ai.workflows.generation.schemas import normalize_draft_payload
from apps.ai.workflows.generation.service import run_test_generation_workflow
from apps.ai.workflows.generation.state import CLOUD_GENERATION_LIMITS
from apps.ai.tasks import _run_generation_session
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import (
    SpecChunk,
    SpecChunkType,
    Specification,
    SpecificationSource,
    SpecificationSourceType,
)
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
        if isinstance(payload, ChatResponse):
            return payload
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return ChatResponse(
            content=content,
            input_tokens=11,
            output_tokens=17,
            finish_reason="stop",
            raw={},
        )


class FailingProvider:
    name = "groq"
    model_name = "llama-3.3-70b-versatile"

    def chat(self, messages, **opts):
        raise LLMProviderRequestError("Provider request timed out.")


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


def make_generation_plan():
    return {
        "objective": "Generate login authentication tests.",
        "context_summary": {"sources": ["prompt"]},
        "candidate_pool": [
            {
                "candidate_id": "cand_login",
                "title": "Login authentication",
                "category": "functional",
                "priority": "must_have",
                "source_refs": [{"type": "objective"}],
                "why_candidate": "Covers the primary authentication journey.",
            },
            {
                "candidate_id": "cand_lockout",
                "title": "Account lockout",
                "category": "security",
                "priority": "should_have",
                "source_refs": [{"type": "objective"}],
                "why_candidate": "Useful security coverage but outside the scenario budget.",
            },
        ],
        "selected_scenarios": [
            {
                "candidate_id": "cand_login",
                "draft_scenario_id": "scenario-login",
                "title": "Login authentication",
                "category": "functional",
                "priority": "must_have",
                "source_refs": [{"type": "objective"}],
                "intended_case_count": 2,
                "why_selected": "Highest-value user-visible login journey.",
            }
        ],
        "excluded_candidates": [
            {"candidate_id": "cand_lockout", "reason": "deferred_under_scenario_budget"}
        ],
        "scenario_budget": {
            "max_scenarios": 5,
            "intended_total_cases": 2,
        },
        "assumptions": [],
        "open_questions": [],
        "termination": {"reason": "planned"},
    }


def make_scenario_expansion(case_ids=None):
    return {
        "scenario": make_valid_draft(case_ids=case_ids)["sections"][0]["scenarios"][0]
    }


def make_requirement_extraction():
    return {
        "requirement_type": "ui_flow",
        "system_or_process_name": "Login",
        "actors": ["Registered user"],
        "business_entities": ["User account"],
        "source_entities": [],
        "target_entities": [],
        "screens": ["Login page", "Dashboard"],
        "apis": [],
        "files_or_reports": [],
        "fields": ["username", "password"],
        "filters": [],
        "grouping_rules": [],
        "sorting_rules": [],
        "calculations": [],
        "business_rules": ["Valid credentials open the dashboard"],
        "validation_rules": ["Invalid passwords show an error message"],
        "update_rules": [],
        "generated_outputs": [],
        "notifications": [],
        "error_conditions": ["Invalid password"],
        "acceptance_criteria": ["Dashboard is displayed after successful login"],
        "test_data_hints": [{"username": "valid.user"}],
        "open_questions": [],
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

    def test_start_generation_accepts_multipart_temporary_attachment(self):
        uploaded = SimpleUploadedFile(
            "orangehrm_requirements.txt",
            b"FR-001: Users can log in with valid OrangeHRM credentials.",
            content_type="text/plain",
        )

        with patch(
            "apps.ai.services.sessions.get_team_brain",
            return_value=FakeProvider([]),
        ), patch("apps.ai.tasks.enqueue_generation_session_task"):
            response = self.client.post(
                reverse("ai-generation-list-create"),
                {
                    "project": str(self.project.id),
                    "objective": "Generate OrangeHRM login tests.",
                    "source_type": AIGenerationSourceType.MIXED,
                    "source_refs": json.dumps(
                        {"repository_context": {"project_id": str(self.project.id)}}
                    ),
                    "temporary_attachments": [uploaded],
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session = AIGenerationSession.objects.get(pk=response.data["id"])
        attachments = session.source_refs["temporary_attachments"]
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "orangehrm_requirements.txt")

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

    def test_temporary_attachment_context_does_not_ingest_specification_rows(self):
        uploaded = SimpleUploadedFile(
            "orangehrm_requirements.txt",
            b"FR-001: Users can log in with valid OrangeHRM credentials.",
            content_type="text/plain",
        )

        with patch(
            "apps.ai.services.sessions.get_team_brain",
            return_value=FakeProvider([]),
        ), patch("apps.ai.tasks.enqueue_generation_session_task"):
            session = start_generation_session(
                user=self.owner,
                project=self.project,
                objective="Generate OrangeHRM login tests.",
                source_type=AIGenerationSourceType.MIXED,
                temporary_attachments=[uploaded],
            )

        session.refresh_from_db()
        self.assertEqual(SpecificationSource.objects.count(), 0)
        self.assertEqual(Specification.objects.count(), 0)
        self.assertEqual(SpecChunk.objects.count(), 0)
        attachments = session.source_refs["temporary_attachments"]
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "orangehrm_requirements.txt")
        self.assertTrue(attachments[0]["fragments"])


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
        fake_provider = FakeProvider(
            [
                make_requirement_extraction(),
                make_generation_plan(),
                make_scenario_expansion(),
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertEqual(session.provider_name, "groq")
        self.assertEqual(session.model_name, "llama-3.3-70b-versatile")
        self.assertEqual(session.input_tokens, 33)
        self.assertEqual(session.output_tokens, 51)
        self.assertEqual(
            fake_provider.calls[0]["opts"]["max_tokens"],
            CLOUD_GENERATION_LIMITS["extraction_max_tokens"],
        )
        self.assertEqual(
            fake_provider.calls[1]["opts"]["max_tokens"],
            CLOUD_GENERATION_LIMITS["planning_max_tokens"],
        )
        plan = session.critic_report["generation_plan"]
        self.assertEqual(plan["schema_version"], "ai_generation_plan_v1")
        self.assertEqual(len(plan["candidate_pool"]), 2)
        self.assertEqual(len(plan["selected_scenarios"]), 1)
        self.assertEqual(len(plan["excluded_candidates"]), 1)
        self.assertTrue(session.retrieved_contexts.exists())

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
            "apps.ai.workflows.generation.context.retrieve_similar_chunks",
            side_effect=RuntimeError("vector search unavailable"),
        ):
            context = retrieve_generation_context(session, top_k=5)

        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["chunk_id"], str(chunk.id))
        stored_context = session.retrieved_contexts.get()
        self.assertEqual(stored_context.object_id, str(chunk.id))

    def test_generation_context_resolves_specification_source_refs(self):
        source = SpecificationSource.objects.create(
            project=self.project,
            name="Imported DOCX",
            source_type=SpecificationSourceType.DOCX,
            uploaded_by=self.owner,
        )
        first_spec = Specification.objects.create(
            project=self.project,
            source=source,
            title="REQ-JOB-1",
            content="The job reads source rows.",
            source_type=SpecificationSourceType.DOCX,
            uploaded_by=self.owner,
        )
        second_spec = Specification.objects.create(
            project=self.project,
            source=source,
            title="REQ-JOB-2",
            content="The job writes generated output.",
            source_type=SpecificationSourceType.DOCX,
            uploaded_by=self.owner,
        )
        first_chunk = SpecChunk.objects.create(
            specification=first_spec,
            chunk_index=0,
            chunk_type=SpecChunkType.FUNCTIONAL_REQUIREMENT,
            content="Read source rows matching the extracted filters.",
        )
        second_chunk = SpecChunk.objects.create(
            specification=second_spec,
            chunk_index=0,
            chunk_type=SpecChunkType.FUNCTIONAL_REQUIREMENT,
            content="Write the generated report output.",
        )
        session = self.make_session(
            objective="Generate job tests for source rows and generated report output.",
            source_refs={"specification_source_id": str(source.id)},
        )

        with patch(
            "apps.ai.workflows.generation.context.retrieve_similar_chunks",
            side_effect=RuntimeError("vector search unavailable"),
        ):
            context = retrieve_generation_context(session, top_k=5)

        self.assertEqual(
            {item["chunk_id"] for item in context},
            {str(first_chunk.id), str(second_chunk.id)},
        )

    def test_invalid_scenario_payload_is_repaired_once(self):
        invalid_expansion = {
            "scenario": {
                "draft_id": "scenario-login",
                "title": "Login authentication",
                "description": "Missing cases should trigger schema repair.",
                "scenario_type": "happy_path",
                "priority": "high",
                "polarity": "positive",
                "cases": [],
            }
        }
        fake_provider = FakeProvider(
            [
                make_requirement_extraction(),
                make_generation_plan(),
                invalid_expansion,
                make_scenario_expansion(),
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.workflows.generation.nodes.context.search_repository_memory",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertEqual(len(fake_provider.calls), 4)
        self.assertEqual(session.draft_payload["sections"][0]["scenarios"][0]["title"], "Login authentication")
        repair_counts = session.critic_report["repair_counts"]["scenario-login"]
        self.assertEqual(repair_counts["schema_repair_attempts"], 1)

    def test_actionable_objective_does_not_stop_on_planner_questions(self):
        timid_plan = {
            "objective": "Generate matricule login tests.",
            "candidate_pool": [],
            "selected_scenarios": [],
            "excluded_candidates": [],
            "scenario_budget": {},
            "assumptions": [],
            "open_questions": [
                "What happens when a user enters a valid matricule but an invalid password?"
            ],
        }
        fake_provider = FakeProvider(
            [
                make_requirement_extraction(),
                timid_plan,
                make_scenario_expansion(),
                make_scenario_expansion(case_ids=["case-negative-a", "case-negative-b"]),
            ]
        )
        session = self.make_session(objective="Generate matricule login tests.")

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.workflows.generation.nodes.context.search_repository_memory",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertFalse(session.critic_report["generation_plan"]["open_questions"])
        self.assertEqual(len(session.critic_report["generation_plan"]["selected_scenarios"]), 2)

    def test_token_truncated_planner_json_retries_with_larger_budget(self):
        fake_provider = FakeProvider(
            [
                make_requirement_extraction(),
                ChatResponse(
                    content='{"objective": "Generate login authentication tests.", "candidate_pool": [',
                    input_tokens=19,
                    output_tokens=1200,
                    finish_reason="MAX_TOKENS",
                    raw={"finishReason": "MAX_TOKENS"},
                ),
                make_generation_plan(),
                make_scenario_expansion(),
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.workflows.generation.nodes.context.search_repository_memory",
            return_value=[],
        ):
            run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.READY_FOR_REVIEW)
        self.assertEqual(len(fake_provider.calls), 4)
        self.assertEqual(
            fake_provider.calls[1]["opts"]["max_tokens"],
            CLOUD_GENERATION_LIMITS["planning_max_tokens"],
        )
        self.assertEqual(
            fake_provider.calls[2]["opts"]["max_tokens"],
            CLOUD_GENERATION_LIMITS["json_retry_max_tokens"],
        )
        self.assertEqual(session.input_tokens, 52)
        self.assertEqual(session.output_tokens, 1251)

    def test_invalid_repair_fails_session_clearly(self):
        invalid_expansion = {
            "scenario": {
                "draft_id": "scenario-login",
                "title": "Login authentication",
                "description": "Missing cases should trigger schema repair.",
                "scenario_type": "happy_path",
                "priority": "high",
                "polarity": "positive",
                "cases": [],
            }
        }
        fake_provider = FakeProvider(
            [
                make_requirement_extraction(),
                make_generation_plan(),
                invalid_expansion,
                invalid_expansion,
                invalid_expansion,
            ]
        )
        session = self.make_session()

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.workflows.generation.nodes.context.search_repository_memory",
            return_value=[],
        ):
            with self.assertRaises(Exception):
                run_test_generation_workflow(str(session.id))

        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.FAILED)
        self.assertTrue(session.error_message)

    def test_task_marks_provider_failure_without_uncaught_crash(self):
        session = self.make_session()

        with patch(
            "apps.ai.workflows.generation.nodes.context.get_team_brain",
            return_value=FailingProvider(),
        ), patch(
            "apps.ai.workflows.generation.nodes.context.retrieve_generation_context",
            return_value=[],
        ), patch(
            "apps.ai.workflows.generation.nodes.context.search_repository_memory",
            return_value=[],
        ):
            result = _run_generation_session(str(session.id))

        session.refresh_from_db()
        self.assertEqual(result["status"], AIGenerationSessionStatus.FAILED)
        self.assertEqual(session.status, AIGenerationSessionStatus.FAILED)
        self.assertIn("timed out", session.error_message)


class AIGenerationCommitTests(AIGenerationTestBase):
    def test_generation_contract_exposes_testing_model_choices(self):
        contract = generation_contract()

        self.assertIn("TestScenario", contract["models"])
        scenario_fields = contract["models"]["TestScenario"]["fields"]
        expected_types = [
            "happy_path",
            "alternative_flow",
            "edge_case",
            "security",
            "performance",
            "accessibility",
        ]
        self.assertEqual(
            [item["value"] for item in scenario_fields["scenario_type"]["choices"]],
            expected_types,
        )
        self.assertEqual(
            SCENARIO_EXPANSION_SCHEMA["properties"]["scenario"]["properties"]["scenario_type"]["enum"],
            expected_types,
        )

    def test_generated_acceptance_test_type_maps_to_canonical_scenario_type(self):
        draft = make_valid_draft(case_ids=["case-acceptance", "case-alternate"])
        draft["sections"][0]["scenarios"][0]["scenario_type"] = "acceptance_test"

        normalized = normalize_draft_payload(draft)

        self.assertEqual(
            normalized["sections"][0]["scenarios"][0]["scenario_type"],
            "happy_path",
        )

    def test_generated_choice_labels_map_to_canonical_database_values(self):
        draft = make_valid_draft(case_ids=["case-labels", "case-labels-negative"])
        scenario = draft["sections"][0]["scenarios"][0]
        scenario["scenario_type"] = "Happy Path"
        scenario["priority"] = "High"
        scenario["business_priority"] = "Must Have"
        scenario["polarity"] = "Positive"

        normalized = normalize_draft_payload(draft)
        normalized_scenario = normalized["sections"][0]["scenarios"][0]

        self.assertEqual(normalized_scenario["scenario_type"], "happy_path")
        self.assertEqual(normalized_scenario["priority"], "high")
        self.assertEqual(normalized_scenario["business_priority"], "must_have")
        self.assertEqual(normalized_scenario["polarity"], "positive")

    def test_generated_priority_label_maps_to_business_priority(self):
        draft = make_valid_draft(case_ids=["case-medium", "case-medium-negative"])
        draft["sections"][0]["scenarios"][0]["business_priority"] = "medium"

        normalized = normalize_draft_payload(draft)

        self.assertEqual(
            normalized["sections"][0]["scenarios"][0]["business_priority"],
            "should_have",
        )

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
        self.assertEqual(
            test_case.steps,
            [
                {"step": "Enter valid username and password.", "outcome": "Credentials are accepted."},
                {"step": "Submit the login form.", "outcome": "Dashboard is displayed."},
            ],
        )
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

    def test_commit_failed_session_with_partial_reviewed_draft(self):
        draft = make_valid_draft(case_ids=["case-partial", "case-unselected"])
        session = self.make_session(
            status=AIGenerationSessionStatus.FAILED,
            draft_payload=draft,
            review_decisions={
                "draft_payload": draft,
                "selected_case_ids": ["case-partial"],
            },
        )

        summary = commit_selected_drafts(session=session)

        self.assertEqual(summary["created_case_count"], 1)
        session.refresh_from_db()
        self.assertEqual(session.status, AIGenerationSessionStatus.SAVED)

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
