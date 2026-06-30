from __future__ import annotations

import httpx
from django.test import SimpleTestCase
from unittest.mock import patch

from apps.ai.providers.base import post_json
from apps.ai.providers.ollama import OllamaProvider
from apps.ai.providers.openai_compatible import OpenAICompatibleProvider
from apps.ai.workflows.generation.evaluations import (
    compare_generation_eval_runs,
    evaluate_generation_draft,
)
from apps.ai.workflows.generation.guardrails import validate_scenario_guardrails
from apps.ai.workflows.generation.quality import evaluate_draft_quality
from apps.ai.workflows.generation.schemas import DraftValidationError, normalize_draft_payload


def minimal_draft(*, scenario_type="happy_path", steps=None):
    return {
        "summary": "Generated coverage.",
        "suite": {"name": "Suite", "description": "Suite description."},
        "sections": [
            {
                "name": "Section",
                "scenarios": [
                    {
                        "title": "Scenario",
                        "description": "Scenario description.",
                        "scenario_type": scenario_type,
                        "priority": "medium",
                        "polarity": "positive",
                        "cases": [
                            {
                                "title": "Case",
                                "preconditions": "Preconditions.",
                                "steps": steps
                                or [
                                    {
                                        "action": "Prepare username field with valid.user.",
                                        "expected": "The username field contains valid.user.",
                                    }
                                ],
                                "expected_result": "Expected result.",
                                "test_data": {},
                            }
                        ],
                    }
                ],
            }
        ],
    }


class ProviderTimeoutTests(SimpleTestCase):
    def test_ollama_uses_local_timeout_and_non_streaming_payload(self):
        provider = OllamaProvider(
            endpoint="http://localhost:11434",
            model_name="mistral",
            temperature=0.1,
            max_tokens=512,
        )

        with patch("apps.ai.providers.ollama.post_json") as post:
            post.return_value = {
                "message": {"content": "{}"},
                "prompt_eval_count": 1,
                "eval_count": 1,
            }
            provider.chat([{"role": "user", "content": "hello"}])

        _, kwargs = post.call_args
        self.assertEqual(kwargs["timeout_seconds"], 300)
        self.assertEqual(kwargs["max_retries"], 0)
        self.assertIs(kwargs["payload"]["stream"], False)

    def test_ollama_chat_json_uses_structured_schema_format(self):
        provider = OllamaProvider(
            endpoint="http://localhost:11434",
            model_name="mistral",
            temperature=0.1,
            max_tokens=512,
        )
        schema = {
            "type": "object",
            "required": ["tool"],
            "properties": {"tool": {"enum": ["browser_snapshot"]}},
        }

        with patch("apps.ai.providers.ollama.post_json") as post:
            post.return_value = {
                "message": {"content": '{"tool": "browser_snapshot"}'},
                "prompt_eval_count": 1,
                "eval_count": 1,
            }
            result = provider.chat_json(
                [{"role": "user", "content": "next action"}],
                schema,
                temperature=0.2,
                max_tokens=128,
            )

        _, kwargs = post.call_args
        self.assertEqual(result, {"tool": "browser_snapshot"})
        self.assertEqual(kwargs["payload"]["format"], schema)
        self.assertIs(kwargs["payload"]["stream"], False)
        self.assertEqual(kwargs["payload"]["options"]["temperature"], 0.2)
        self.assertEqual(kwargs["payload"]["options"]["num_predict"], 128)

    def test_openai_compatible_keeps_cloud_timeout_and_rate_limit_retries(self):
        provider = OpenAICompatibleProvider(
            name="groq",
            api_key="test",
            model_name="llama-3.3-70b-versatile",
            base_url="https://api.groq.com/openai/v1",
            temperature=0.1,
            max_tokens=512,
        )

        with patch("apps.ai.providers.openai_compatible.post_json") as post:
            post.return_value = {
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
            provider.chat([{"role": "user", "content": "hello"}])

        _, kwargs = post.call_args
        self.assertEqual(kwargs["timeout_seconds"], 90)
        self.assertEqual(kwargs["max_retries"], 3)

    def test_post_json_retries_429_using_try_again_delay(self):
        request = httpx.Request("POST", "https://example.test/chat")
        responses = [
            httpx.Response(429, request=request, text="rate limit, try again in 2s"),
            httpx.Response(200, request=request, json={"ok": True}),
        ]
        calls = []

        class FakeClient:
            def __init__(self, **kwargs):
                calls.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, *args, **kwargs):
                return responses.pop(0)

        with patch("apps.ai.providers.base.httpx.Client", FakeClient), patch(
            "apps.ai.providers.base.time.sleep"
        ) as sleep:
            result = post_json(
                url="https://example.test/chat",
                payload={"messages": []},
                headers={},
                max_retries=1,
            )

        self.assertEqual(result, {"ok": True})
        sleep.assert_called_once_with(3.0)
        self.assertEqual(calls[0]["timeout"], 90)

    def test_post_json_retries_429_using_millisecond_delay(self):
        request = httpx.Request("POST", "https://example.test/chat")
        responses = [
            httpx.Response(
                429,
                request=request,
                text='{"error":{"message":"Rate limit reached. Please try again in 674.999999ms."}}',
            ),
            httpx.Response(200, request=request, json={"ok": True}),
        ]

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, *args, **kwargs):
                return responses.pop(0)

        with patch("apps.ai.providers.base.httpx.Client", FakeClient), patch(
            "apps.ai.providers.base.time.sleep"
        ) as sleep:
            result = post_json(
                url="https://example.test/chat",
                payload={"messages": []},
                headers={},
                max_retries=1,
            )

        self.assertEqual(result, {"ok": True})
        sleep.assert_called_once_with(1.674999999)


class DraftSchemaQualityTests(SimpleTestCase):
    def test_steps_normalize_to_one_based_action_expected_outcome_shape(self):
        normalized = normalize_draft_payload(
            minimal_draft(
                steps=[
                    {
                        "step_index": 0,
                        "step": "Prepare username field with valid.user.",
                        "expected": "The username field contains valid.user.",
                        "target": "username",
                    },
                    {
                        "description": "Submit password field with secret.",
                        "expected_result": "The dashboard opens.",
                    },
                ]
            )
        )

        steps = normalized["sections"][0]["scenarios"][0]["cases"][0]["steps"]
        self.assertEqual(steps[0]["step_index"], 1)
        self.assertEqual(steps[1]["step_index"], 2)
        self.assertEqual(steps[0]["action"], "Prepare username field with valid.user.")
        self.assertEqual(
            steps[0]["expected_outcome"],
            "The username field contains valid.user.",
        )
        self.assertEqual(steps[0]["target"], "username")

    def test_missing_step_expected_outcome_fails_validation(self):
        with self.assertRaises(DraftValidationError):
            normalize_draft_payload(
                minimal_draft(steps=[{"action": "Prepare username field."}])
            )

    def test_scenario_type_aliases_normalize_to_existing_choices(self):
        normalized = normalize_draft_payload(minimal_draft(scenario_type="error_case"))
        scenario = normalized["sections"][0]["scenarios"][0]
        self.assertEqual(scenario["scenario_type"], "edge_case")

    def test_unknown_scenario_type_still_fails(self):
        with self.assertRaises(DraftValidationError):
            normalize_draft_payload(minimal_draft(scenario_type="surprise_case"))

    def test_vague_step_quality_gate_warns_without_crashing(self):
        normalized = normalize_draft_payload(
            minimal_draft(
                steps=[
                    {
                        "action": "Enter valid data into the system.",
                        "expected_outcome": "The application shows the expected state.",
                    }
                ]
            )
        )
        result = evaluate_draft_quality(
            normalized,
            {
                "requirement_type": "batch_job",
                "system_or_process_name": "Nightly billing job",
                "source_entities": ["Invoice table"],
                "fields": ["invoice_id"],
                "update_rules": ["LAST_RUN_DATE is set to system date"],
            },
        )

        self.assertTrue(result.should_repair)
        self.assertTrue(result.vague_steps)
        self.assertIn("Draft contains generic steps", result.warnings[0])

    def test_generation_guardrails_detect_missing_traceability_and_vague_expected_result(self):
        scenario = {
            "draft_id": "scenario-registration",
            "title": "Registration validation",
            "description": "Registration validation.",
            "scenario_type": "alternative_flow",
            "priority": "high",
            "polarity": "negative",
            "cases": [
                {
                    "draft_id": "case-no-trace",
                    "title": "Reject duplicate username and then reject missing username",
                    "preconditions": "",
                    "steps": [
                        {
                            "action": "Submit duplicate registration data.",
                            "expected_outcome": "Expected state is shown.",
                        }
                    ],
                    "expected_result": "Works correctly.",
                    "test_data": {},
                    "coverage": {"evidence_ids": []},
                }
            ],
        }

        result = validate_scenario_guardrails(
            scenario_payload=scenario,
            scenario_plan={
                "scenario_type": "alternative_flow",
                "covered_obligation_ids": ["OBL-1"],
                "requirement_ids": [],
                "source_type": "explicit_requirement",
            },
            coverage_obligations=[
                {
                    "obligation_id": "OBL-1",
                    "behavior": "Registration rejects duplicate usernames.",
                    "expected_outcome": "Duplicate usernames are rejected.",
                    "requirement_ids": [],
                }
            ],
        )

        codes = {item.code for item in result.violations}
        self.assertIn("missing_requirement_references", codes)
        self.assertIn("missing_case_detail", codes)
        self.assertIn("vague_expected_result", codes)
        self.assertIn("combined_non_atomic_objective", codes)
        self.assertTrue(result.should_repair)

    def test_generation_eval_reports_metrics_and_deltas(self):
        dataset = {
            "dataset_id": "registration",
            "expected": {
                "requirement_ids": ["FR-AUTH-001", "FR-AUTH-002"],
                "categories_by_requirement": {
                    "FR-AUTH-001": "happy_path",
                    "FR-AUTH-002": "alternative_flow",
                },
            },
        }
        before = minimal_draft()
        after = minimal_draft()
        scenario = after["sections"][0]["scenarios"][0]
        scenario["scenario_type"] = "happy_path"
        case = scenario["cases"][0]
        case["expected_result"] = "The registration confirmation is displayed."
        case["coverage"] = {
            "requirement_ids": ["FR-AUTH-001"],
            "evidence_ids": ["FR-AUTH-001"],
            "source_type": "explicit_requirement",
        }

        before_metrics = evaluate_generation_draft(dataset=dataset, draft_payload=before)
        after_metrics = evaluate_generation_draft(dataset=dataset, draft_payload=after)
        delta = compare_generation_eval_runs(before=before_metrics, after=after_metrics)

        self.assertEqual(after_metrics["traceability_rate"], 1.0)
        self.assertEqual(after_metrics["requirement_coverage"], 0.5)
        self.assertGreater(delta["traceability_rate"], 0)
