# AI layer reference

Deep dive on `apps/ai/`. Read before changing prompts, providers, the generation graph, or browser authoring.

## Provider abstraction (`apps/ai/providers/`)

- **`base.py`** — `LLMProvider` Protocol with `name`, `model_name`, `chat(messages, **opts) -> ChatResponse`, `chat_json(messages, schema, **opts) -> ChatResponse`. `ChatResponse` is `{content, input_tokens, output_tokens, finish_reason, raw}`. Exceptions: `LLMProviderError`, `LLMProviderNotConfiguredError`, `LLMProviderRequestError`, `LLMProviderResponseError`. The `post_json()` helper is **429-aware**: it parses both the `retry-after` header and the "try again in Xs" regex in error bodies. `parse_json_content()` attempts a clean JSON parse, then falls back to brace extraction for models that wrap output in prose.

- **`factory.py`** — `get_llm_provider(team, purpose=ModelProfilePurpose.DEFAULT)`. Resolution order:
  1. Fetch `TeamAIConfig`; raise `LLMProviderNotConfiguredError` if disabled / unconfigured / no API key.
  2. Pick a `ModelProfile` by `purpose`; fall back to `TeamAIConfig.default_model_profile_id`; final fallback `is_default=True`.
  3. Read `model_name` (default `gpt-3.5-turbo`), `temperature` (default `0.10`), `max_tokens` (default `4096`).
  4. Dispatch by `provider_type`:
     - `ollama` → `OllamaProvider` (endpoint = config.endpoint_url or provider.base_url or `DEFAULT_OLLAMA_ENDPOINT`)
     - `openai` / `groq` → `OpenAICompatibleProvider` (Groq quirk: uses `max_completion_tokens` instead of `max_tokens`)
     - `azure_openai` → `AzureOpenAIProvider` (uses `deployment_name`, not `model_name`)
     - `anthropic` → `AnthropicProvider`

- **`openai_compatible.py`** — POST `/chat/completions`, timeout 90s, `max_retries=1`. Parses `raw["choices"][0]["message"]["content"]`. Tokens from `prompt_tokens` / `completion_tokens`.

- **`ollama.py`** — POST `/api/chat`, timeout 300s, no retries, `stream=False`. Body uses `options.temperature`, `options.num_predict` (for max_tokens), optional `options.num_ctx`. Parses `raw["message"]["content"]`. Tokens from `prompt_eval_count` / `eval_count`. Overrides `chat_json()` to set `format="json"` and inject schema into the system message.

- **`anthropic.py`** — POST `/messages` with `x-api-key` and `anthropic-version: 2023-06-01`. Separates `role="system"` into a top-level `system` field; converts user/assistant roles. Parses `raw["content"]` array of text parts.

- **`azure_openai.py`** — POST `/openai/deployments/{deployment}/chat/completions?api-version={version}` with `api-key` header. Otherwise identical to OpenAI-compatible.

- **`apps/ai/services/brain.py`** — `get_team_brain = get_llm_provider`. Use this when speaking the documented vocabulary (`docs/architecture/07-ai-layer.md` calls it the "team brain").

## ModelProfile purposes

`accounts.models.ModelProfilePurpose` ∈ {`test_design`, `review`, `execution`, `default`}. Recommended runtime mapping (verify quotas in each provider's dashboard — free tiers shift):

| Purpose | Provider | Suggested model | Why |
|---|---|---|---|
| `test_design` | Google AI Studio (OpenAI-compatible) | `gemini-2.0-flash` | Generous free tier, strong JSON-mode, fits Phase D per-group fan-out |
| `review` (critic) | GitHub Models (Azure-OpenAI-compatible) | `gpt-4o` | Highest free quality; low daily quota is fine for one critic pass per session |
| `execution` (browser authoring) | Cerebras Cloud (OpenAI-compatible) | `llama-3.3-70b` | Sub-second latency for per-step loop, separate rate bucket from Groq |
| `default` (fallback) | OpenRouter (OpenAI-compatible) | `meta-llama/llama-3.3-70b-instruct:free` | One key rotates across many free models |

Local fallback:
- `ollama:qwen2.5-coder:7b` — good for browser-authoring per-step decisions (small schema)
- `ollama:qwen2.5:14b-instruct-q4` — usable for Phase D when no cloud key
- **Do not use `mistral:7b` for test_design** — JSON adherence and multi-step reasoning are too weak

## Models (`apps/ai/models.py`)

- **AIGenerationSession** (UUID PK)
  - FKs: `team`, `project`, `created_by` (nullable), `target_suite` (nullable), `target_section` (nullable), `attached_specification` (nullable)
  - Status: `QUEUED` / `GENERATING` / `READY_FOR_REVIEW` / `REVIEWING` / `SAVED` / `FAILED` / `CANCELLED`
  - Source types: `PROMPT` / `SPECIFICATION` / `JIRA` / `MANUAL` / `MIXED`
  - JSON fields: `source_refs`, `draft_payload`, `critic_report`, `review_decisions`, `saved_object_ids`
  - Counters / telemetry: `provider_name`, `model_name`, `purpose`, `prompt_version`, `schema_version`, `input_tokens`, `output_tokens`, `duration_ms`, `mlflow_run_id`, `trace_id`
  - Indexed on `(team, status)` and `(project, created_at)`

- **AIGenerationRetrievedContext** (UUID PK, cascade from session)
  - `context_type` ∈ {`SPEC_CHUNK`, `TEST_SUITE`, `TEST_SCENARIO`, `TEST_CASE`, `REPOSITORY_MEMORY`, `JIRA`, `GITHUB`, `PROMPT`}
  - `object_id`, `external_ref`, `score` (float), `metadata_json`

## Test generation workflow

Located at `apps/ai/services/test_generation_workflow.py` + `apps/ai/graphs/test_generation_graph.py`. LangGraph state is a `TypedDict` with the session, provider, generation_limits (CLOUD vs LOCAL), rag_context, repository_memory, normalized_intent, requirement_extraction, raw_draft_payload, draft_payload, critic_report, validation_error, quality_warnings, token accumulators, mlflow_run_id.

Generation limits (cloud / local):
- max_sections: 5 / 2
- scenarios_per_section: 8 / 3
- cases_per_scenario: 6 / 2
- steps_per_case: 12 / 6
- rag_top_k: 12 / 5
- chunk_chars: 1000 / 650
- extraction_max_tokens: 1200 / 700
- design_max_tokens: 4096 / 1800
- repair_max_tokens: 3000 / 1400
- critic_max_tokens: 1600 / 0

The 14 graph nodes in order:

1. **`request_gate`** — validates FK consistency (team, project, suite, section, spec), sets status → `GENERATING`, sets `started_at`.
2. **`brain_resolver`** — resolves provider with `purpose=TEST_DESIGN`; picks LOCAL limits if `provider_type=="ollama"` else CLOUD. Saves provider/model/purpose to the session.
3. **`capacity_check`** — re-runs `services/capacity.check_ai_generation_capacity` (default cap 20 active sessions per team).
4. **`context_retrieval`** — `services/context_retrieval.retrieve_generation_context()`. Modes: single spec (vector similarity, fallback keyword), multi-spec bundle, full-source bundle (≤30 chunks ordered by spec title + chunk_index). Creates `AIGenerationRetrievedContext` per chunk.
5. **`repository_memory_search`** — `services/repository_memory.search_repository_memory()`. Token-overlap rank on 250 newest TestCases per project.
6. **`intent_normalizer`** — builds `normalized_intent` dict.
7. **`requirement_extraction`** — LLM call with `REQUIREMENT_EXTRACTION_SCHEMA` (20 fields: actors, business_entities, screens, apis, files_or_reports, fields, filters, grouping_rules, sorting_rules, calculations, business_rules, validation_rules, update_rules, generated_outputs, notifications, error_conditions, acceptance_criteria, test_data_hints, open_questions, plus `requirement_type` ∈ {ui_flow, batch_job, api, data_processing, integration, reporting, security_access_control, validation_rules, unknown}).
8. **`test_design_generator`** — LLM call with `DRAFT_JSON_SCHEMA`. **Phase D Step 1 will fan this out into per-requirement-group calls.**
9. **`draft_schema_validator`** — `schemas/test_generation_draft_v1.normalize_draft_payload()`. Validates structure, generates `draft_id` UUIDs, applies scenario_type aliases (`error_case` → `EDGE_CASE`, etc.), enforces array limits. Raises `DraftValidationError` on mismatch.
10. **`draft_repair`** — LLM repair call when validation fails. Re-runs the validator.
11. **`draft_quality_gate`** — `services/draft_quality.evaluate_draft_quality()`. 14-phrase vague-step detector ("enter valid data", "verify the result", etc.), grounding check against requirement_extraction facts, "too shallow" warning. `should_repair = vague OR not_grounded OR too_shallow`.
12. **`quality_repair`** — second LLM pass with explicit repair instruction from `format_quality_repair_instruction(result)`. Re-evaluates quality.
13. **`test_critic`** — **disabled by default** via `AI_GENERATION_ENABLE_CRITIC=False`. When enabled: judges duplicates, missing negative/edge, weak expected results, unclear preconditions, inconsistent priority. Merges critic-suggested fixes back into the draft.
14. **`persist_ready_for_review`** — saves `draft_payload`, `critic_report` (with `quality_warnings`), token counts, `mlflow_run_id`, `completed_at`. Status → `READY_FOR_REVIEW`.

Workflow entry: `run_test_generation_workflow(session_id)` wraps the graph in an MLflow run context. On exception: `mark_generation_failed(session_id, error_msg, state=state)`.

LLM helpers in the same module:
- `_call_llm_json(provider, messages, schema, allow_invalid_json=False, max_tokens=None, num_ctx=None)` prepends a system prompt with the schema JSON, sets `response_format={"type": "json_object"}`, parses with `parse_json_content()`. If `allow_invalid_json=True` and parsing fails, returns `{"_invalid_json_content": content}` instead of raising. Measures duration via `time.monotonic()`.
- `_accumulate_usage(state, result)` sums input/output tokens and duration_ms.

## Draft schema (`schemas/test_generation_draft_v1.py`)

`SCHEMA_VERSION = "ai_generation_draft_v1"`. `DRAFT_JSON_SCHEMA` top-level required: `summary`, `suite`, `sections`. Optional top-level: `assumptions`, `open_questions`, `requirement_extraction`.

Each section: `draft_id`, `name` (required), `scenarios`, `children` (nested sections).
Each scenario: `draft_id`, `title`, `description`, `scenario_type` (`ALLOWED_SCENARIO_TYPES` enum), `priority`, `business_priority`, `polarity`, `confidence`, `possible_duplicates`, `cases` (required).
Each case: `draft_id`, `title`, `preconditions`, `steps` (each: `action` and `expected_outcome` required, plus optional `step_index`, `target`, `test_data`, `validation_type`, `notes`), `expected_result`, `test_data`, `linked_spec_ids`, `possible_duplicates`.

`normalize_draft_payload(payload)` validates against `DRAFT_JSON_SCHEMA` (jsonschema), generates `draft_id` UUIDs where missing, applies scenario_type aliases, enforces array length limits, raises `DraftValidationError` on mismatch.

## Prompts

All under `apps/ai/prompts/`:

- `requirement_extraction_v1.py` — `EXTRACTION_PROMPT_VERSION="requirement_extraction_v1"`. 20-field schema with `requirement_type` enum. Each field is `array of (string | object)`. Empty default for all fields is `[]`. **Phase D Step 2 will promote to `_v2` with few-shot examples.**
- `test_design_v1.py` — `DESIGN_PROMPT_VERSION="test_design_v1"`. System prompt directs: ground in requirement_extraction + repo memory, avoid duplicates, concrete assertions, process vs UI branching by `requirement_type`, obey generation_limits. User prompt is JSON-shaped (objective + normalized_intent + requirement_extraction + rag_context + repository_memory + generation_limits + allowed_scenario_types).
- `test_critic_v1.py` — `CRITIC_PROMPT_VERSION="test_critic_v1"`. Reviews for duplicates, missing negative/edge, weak expected results. Output JSON: `{critic_report, draft_payload}` (same schema, small fixes only).
- `browser_authoring_v1.py` — `BROWSER_AUTHORING_PROMPT_VERSION="browser_authoring_v1"`. `ALLOWED_BROWSER_ACTIONS = {navigate, click, fill, select, wait, assert_visible, assert_text, stop, ask_user}`. `BROWSER_ACTION_SCHEMA` required = `[action, reason]`, optional = `element_id, element_ref, ref, selector, value, url, assertion, success, message`. System prompt rules: use element_ref/ref from `observation.interactive_elements`, do not invent CSS selectors, `stop` only when the test goal is verified, `ask_user` only when manual input blocks progress.

## Browser authoring (`apps/ai/services/browser_authoring*.py`)

Real Playwright MCP via stdio. **No Selenium fallback.**

### `PlaywrightMCPClient` (`browser_authoring_tools.py:32-164`)

- Constructor: `command`, `args`, `env`, `start_timeout_seconds=30`, `call_timeout_seconds=30`.
- `start()` spawns a daemon thread that runs an asyncio loop, waits on `_ready` event.
- `_async_start()` is the key sequence:
  1. Imports `mcp.ClientSession`, `mcp.StdioServerParameters`, `mcp.client.stdio.stdio_client`
  2. Creates `StdioServerParameters(command, args, env)`
  3. **Opens `errlog = self._open_mcp_errlog()`** — opens a real file handle (either `settings.AI_PLAYWRIGHT_MCP_LOG_FILE` or `os.devnull`) and passes it to `stdio_client(server_params, errlog=errlog)`. **This dodges Celery's LoggingProxy.fileno() problem** — Celery replaces `sys.stderr` with a `LoggingProxy` that has no `fileno()`, which would crash MCP stdio startup if forwarded.
  4. Wraps streams in `ClientSession`, calls `session.initialize()`, calls `list_tools()`, stores tool schemas.
- `call_tool(name, arguments)` uses `asyncio.run_coroutine_threadsafe` with `call_timeout_seconds`.

### `PlaywrightMCPBrowserAuthoringTool` (`browser_authoring_tools.py:168-327`)

- `start()` instantiates client from `settings.AI_PLAYWRIGHT_MCP_COMMAND` (`npx`) + `AI_PLAYWRIGHT_MCP_ARGS` (`["@playwright/mcp@latest", "--headless"]`).
- `observe()` calls MCP `browser_snapshot`; extracts Page URL, Page Title; compacts snapshot to 4000 chars; extracts up to 80 interactive_elements by parsing `[ref=...]` tags.
- `execute(action, observation)` routes by `action["action"]` to MCP tools: `browser_navigate`, `browser_click`, `browser_type`, `browser_select_option`, `browser_wait_for`. `assert_text` / `assert_visible` evaluated locally against the snapshot. Resolves element refs from `observation.interactive_elements` via fuzzy name/role/line match.
- `get_stream_session_id()` returns `None` — **placeholder until Phase E Step 2** wires the containerized MCP allocator.
- `close()` calls `browser_close` MCP tool if present, closes the exit stack.

### Orchestration (`browser_authoring.py`)

- `start_browser_authoring_session(user, test_case, target_url, max_steps=12, browser, platform)`:
  1. `can_trigger_test_execution(user, test_case)` permission check
  2. Resolves the `EXECUTION` brain early to fail fast on config errors
  3. `get_or_create_adhoc_run_case(test_case, triggered_by=user)`
  4. Creates `TestExecution(status=QUEUED, stream_enabled=True)`
  5. `publish_execution_status_changed(execution)`
  6. `enqueue_authoring_session_task(execution_id, target_url, max_steps=_bounded_max_steps(max_steps))`. **Phase E Step 3 will wrap this in `transaction.on_commit(...)`.**
  7. On exception → `finalize_execution_result(status=ERROR, ...)` with stack trace

- `run_browser_authoring_session(execution_id, target_url, max_steps, browser_tool_factory, provider)`:
  1. `TestExecution.objects.select_related(...).get(pk=execution_id)` — **no `DoesNotExist` guard yet** (Phase E Step 3 adds one).
  2. Returns early if `status == CANCELLED`.
  3. Resolves `EXECUTION` brain; instantiates tool via factory.
  4. Status → `RUNNING`, `started_at = timezone.now()`.
  5. `tool.start()` → `_cache_session_if_available()` (no-op today since `get_stream_session_id()` returns None).
  6. Step 1 navigates to `target_url`, records `ExecutionStep(action="navigate", status=PASSED)`.
  7. Loop steps 2..max_steps:
     - Refresh `status` and `pause_requested`; return early if CANCELLED.
     - `observation = tool.observe()`
     - `decision = _next_browser_action(provider, goal, observation, trace[-6:], max_steps)` — LLM call with `max_tokens=500` and **no explicit temperature override** (uses ModelProfile default).
     - `action == "stop"` → `finalize_execution_result(PASSED|FAILED)`.
     - `action == "ask_user"` → status `PAUSED`, record PENDING step, return.
     - Otherwise → `tool.execute(decision, observation)` → record PASSED step + publish.
     - Exceptions during execute → record FAILED step + `finalize_execution_result(FAILED)`.
  8. If loop exhausts without `stop` → `finalize_execution_result(FAILED, "AI authoring reached the maximum step count...")`.
  9. `finally: tool.close()` — must always run to close the MCP exit stack.

- `save_authoring_trace_as_draft_steps(execution, user)`:
  1. `can_manage_test_case_record(user, test_case)` permission check
  2. Query PASSED `ExecutionStep`s ordered by `step_index`
  3. `_trace_step_to_case_step(step)` maps each action to a `{step, outcome}` dict via per-action templates
  4. `update_test_case_with_revision(test_case, steps=..., design_status=DRAFT, created_by=user, source_snapshot_json={"mutation_source": "ai_browser_authoring_trace", "authoring_execution_id": str(execution.id)})` — creates a new revision, resets design_status to DRAFT
  5. Returns `{test_case_id, revision_id, version, step_count, steps}`

## Celery tasks (`apps/ai/tasks.py`)

- `@shared_task(bind=True, name="ai.run_generation_session")` `run_generation_session_task(session_id)` → `run_test_generation_workflow(session_id)`. Returns `{session_id, status, error_message}`.
- `@shared_task(bind=True, name="ai.run_authoring_session")` `run_authoring_session_task(execution_id, target_url, max_steps)` → `run_browser_authoring_session(...)`. Returns `{execution_id, status}`.

Enqueue helpers `enqueue_generation_session_task` and `enqueue_authoring_session_task`:
- Try `.delay()`.
- Fall back to eager call when `DEBUG=True` or `CELERY_TASK_ALWAYS_EAGER`.
- Raise `RuntimeError` otherwise.

## REST endpoints (`apps/ai/urls.py` + `views.py`)

```
GET    /ai/generations/                                   list (filter by ?project=)
POST   /ai/generations/                                   start (AIGenerationSessionStartSerializer)
GET    /ai/generations/{id}/                              detail (frontend polls every 1.8s)
PATCH  /ai/generations/{id}/review/                       apply review decisions
POST   /ai/generations/{id}/commit/                       commit_selected_drafts (only AI → canonical writer)
POST   /ai/authoring/sessions/                            start_browser_authoring_session
POST   /ai/authoring/sessions/{execution_id}/save-trace/  save_authoring_trace_as_draft_steps
```

`AIGenerationSessionStartSerializer` input: `project` (UUID, required), `objective` (string), `source_type` (default `PROMPT`), optional `target_suite`, `target_section`, `attached_specification`, `source_refs`, `jira_issue_key`.

`AIAuthoringSessionStartSerializer` input: `test_case` (UUID), `target_url`, optional `max_steps`, `browser`, `platform`.

`AICapacityExceededError` is converted to HTTP 429 with `Retry-After` header by the views.

## Tests

- `apps/ai/tests/test_generation_workflow.py` — capacity, permission, full graph invocation with a FakeProvider, status transitions, token accumulation, payload structure, `commit_selected_drafts` tree traversal.
- `apps/ai/tests/test_browser_authoring.py` — `start_browser_authoring_session` permission, FakeBrowserTool-driven `run_browser_authoring_session` (start/observe/execute), LLM action parsing, trace building, `save_authoring_trace_as_draft_steps` step conversion. **MCP integration is not exercised in unit tests** — only the protocol contract via the fake.
- `apps/ai/tests/test_provider_and_draft_quality.py` — Ollama timeout=300s no-retry stream-false, OpenAI-compatible timeout=90s max_retries=1, vague-step detection, fact grounding, `normalize_draft_payload` validation.

## Phase D / Phase E split — do not blur

- **Phase D** = Specifications → reviewable logical test design tree (`TestSuite → Section → Scenario → Case` with logical steps, expected results, test data ideas, coverage of negative / edge / security / performance / accessibility when relevant). Output is `draft_payload` on `AIGenerationSession`. Ships first.
- **Phase E** = takes **one selected logical TestCase** that Phase D produced and a human approved, drives Playwright MCP to record real browser actions, saves trace as a new `TestCaseRevision` (`design_status=DRAFT`). Later (Step 4B in `docs/roadmap.md`): trace translated into Selenium `AutomationScript` on the same TestCase.
- **Phase F** = self-healing. Spec in `docs/backlog.md`. Out of scope until Phase D + E are solid.
