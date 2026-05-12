# 03 — Domain Model

**Every model. Every relationship. Every invariant. The canonical data hierarchy.**

---

## 1. The canonical hierarchy

```
Organization
  └─ Team ── TeamAIConfig ── ModelProfile ── AIProvider
       │   └─ IntegrationConfig
       │   └─ ExecutionEnvironment (team-scoped)
       └─ Project
            ├─ ProjectMember
            ├─ Specification ── SpecChunk (pgvector)
            │     └─ SpecificationSource ── SpecificationSourceRecord
            ├─ TestSuite
            │   └─ TestSection (can nest)
            │       └─ TestScenario
            │           └─ TestCase
            │                 └─ TestCaseRevision (immutable snapshots)
            │                       └─ AutomationScript (pinned to a revision)
            ├─ TestPlan
            │   └─ TestRun (run_kind: planned | standalone | system_generated)
            │       └─ TestRunCase  ←── pins (TestCase, TestCaseRevision)
            │             └─ TestExecution
            │                   ├─ TestResult
            │                   ├─ ExecutionStep (many)
            │                   ├─ TestArtifact (many — keys into MinIO)
            │                   └─ ExecutionCheckpoint (many)
            ├─ ExecutionSchedule
            ├─ RepositoryBinding
            ├─ WebhookEvent
            ├─ ExternalIssueLink
            └─ IntegrationActionLog

UserProfile ── UserIntegrationCredential (personal, encrypted)
```

---

## 2. Tenancy and identity (`accounts` app)

### 2.1 `Organization`
Top-level tenant. One organization = one customer. Owns all teams and users.

### 2.2 `Team`
Belongs to an organization. Scopes AI config, integrations, and project access.
- `manager` — display-only pointer (NOT authority — see RBAC)
- `name`, `description`, timestamps

### 2.3 `TeamMembership`
The **authority record** for team-level role.
- `team`, `user`
- `role` — `manager` | `member` | `viewer`
- `is_primary` — UI default context
- `is_active` — soft-delete

This is the source of truth for "who manages this team." `Team.manager` is just a UI pointer.

### 2.4 `UserProfile`
Extends Django's `User`. Holds:
- `organization` (FK)
- `organization_role` — `platform_owner` | `org_admin` | `member`
- Notification preferences (provider, slack/teams IDs)
- Personal integration tokens are NOT here (they're in `UserIntegrationCredential`)

### 2.5 `ProjectMember`
Project-level membership.
- `project`, `user`
- `role` — `manager` | `member` | `viewer`

### 2.6 `TeamAIConfig` (one per team)
Per-team AI configuration:
- `provider` — references `AIProvider`
- encrypted `api_key`, `endpoint_url`, `api_version`
- `monthly_budget`
- default and per-purpose model profiles through `ModelProfile`

The actual API key lives encrypted on `TeamAIConfig`, not on `Team`, `ModelProfile`, or `AIProvider`. See [`07-ai-layer.md`](07-ai-layer.md).

### 2.7 `ModelProfile`
Per-purpose model assignment:
- `team_ai_config` (FK)
- `purpose` — `test_design` | `review` | `execution`
- `deployment_mode` — `local` | `cloud`
- `model_name` (e.g., `claude-opus-4-7`, `llama3:70b`)

A team has multiple `ModelProfile`s — one per purpose. Test design might use a small local model; execution analysis might use a large cloud model.

### 2.8 `AIProvider`
Reference data: known AI providers and their default endpoints. Anthropic, OpenAI, Ollama, Mistral, etc.

### 2.9 `UserIntegrationCredential`
Per-user encrypted credentials for integrations (e.g., a personal Jira API token used when a tester wants to act-as-themselves on Jira). **Never returned by any API serializer.**

### 2.10 `AIGenerationSession` (Step 4A)
Temporary workflow state for offline AI test generation.
- Stores prompt/objective, source refs, status, provider/model snapshot, draft payload, critic report, review decisions, saved object IDs, token/latency/error summaries
- Drafts stay here until a user explicitly commits selected items
- On commit, selected drafts become canonical `TestSuite`, root or child `TestSection`, `TestScenario`, `TestCase`, and `TestCaseRevision` rows

### 2.11 `AIGenerationRetrievedContext` (Step 4A)
Audit trail of what grounded a generation session.
- Links a session to retrieved `SpecChunk`, existing test/repository memory, or external references
- Does not replace `SpecChunk`, `TestCase`, or integration action logs

---

## 3. Projects (`projects` app)

### 3.1 `Project`
- `team` (FK)
- `name`, `description`, `status`, archive flags
- `created_by`, timestamps

### 3.2 `ProjectMember`
See above. Granular project-level access on top of team membership.

---

## 4. Specifications (`specs` app)

### 4.1 `SpecificationSource`
A source document or URL that hasn't been imported yet. Holds the raw upload.
- `project` (FK)
- `source_type` — `pdf` | `docx` | `xlsx` | `csv` | `url` | `jira`
- `parser_status` — `pending` | `parsing` | `parsed` | `failed`
- File reference, original metadata

### 4.2 `SpecificationSourceRecord`
The parser's intermediate output: structured rows extracted from a source, awaiting human review before becoming canonical.
- `source` (FK)
- `status` — `pending_review` | `imported` | `rejected`
- `extracted_content`, `extracted_metadata`

### 4.3 `Specification`
Canonical, imported specification.
- `project` (FK)
- `title`, `body`, `tags`, source metadata
- `index_status` — `unindexed` | `indexing` | `indexed` | `failed`

### 4.4 `SpecChunk`
Embedded chunks of a specification, indexed in pgvector.
- `specification` (FK)
- `chunk_type` — paragraph / heading / list / table cell
- `content` (text)
- `embedding` (1024-dim vector — `BAAI/bge-m3`)
- HNSW cosine index

Default API responses do **not** return embeddings (heavy payload).

### 4.5 `EmbeddingModel`
Reference data: known embedding models, their dimensions, MLflow run id for telemetry.

### 4.6 Indexing service rules
- Idempotent — re-indexing a spec replaces its chunks atomically
- MLflow logs every embedding run
- Chunking config: `SPEC_CHUNK_MAX_CHARS=1400`, `SPEC_CHUNK_OVERLAP_CHARS=120` (sentence-window)
- See [`09-specs-and-rag.md`](09-specs-and-rag.md)

---

## 5. Test repository (`testing` app, repository half)

### 5.1 `TestSuite`
Top of the test hierarchy within a project.
- `project` (FK)
- `name`, `description`
- `created_by`, timestamps

### 5.2 `TestSection`
Folder-like grouping inside a suite. Can nest.
- `suite` (FK)
- `parent` (FK self) — `null` means root
- `name`, `description`, `order_index`

### 5.3 `TestScenario`
A specific user-flow scope.
- `section` (FK)
- `name`, `description`
- `business_priority`, `polarity` (positive/negative), `scenario_type`
- `order_index`

### 5.4 `TestCase` — the **live editable design record**
The canonical test case, mutable.
- `scenario` (FK)
- `title`, `preconditions`, structured `steps`, `expected_result`, `test_data`
- `design_status` — `draft` | `approved` | `archived`
- `automation_status` — `manual` | `automated` | `unautomatable`
- `on_failure` — `stop` | `continue`
- `timeout_ms`, `version_number`
- `linked_specifications` (M2M to `Specification`)

### 5.5 `TestCaseRevision` — the **immutable execution-truth snapshot**
A frozen copy of `TestCase` at the moment a revision-worthy field changed.
- `test_case` (FK)
- `version_number` (monotonic per case)
- Snapshots: `title`, `preconditions`, `steps`, `expected_result`, `test_data`
- `linked_specifications_snapshot` (snapshot of M2M)
- `source_metadata`
- `created_at` (immutable)

**Invariant:** revision rows are never modified after creation. Repository services enforce this.

### 5.6 Why two records (TestCase vs TestCaseRevision)?
The case is what the QA team **edits**. The revision is what executions **point to**. When a test runs and fails six months later, you need to know exactly what the case said when the run started — not what the case says today. Without revisions, every edit retroactively changes the meaning of every past run.

This is the most important invariant in the data model. Don't compromise it.

---

## 6. Planning + Runs (`testing` app, planning half)

### 6.1 `TestPlan`
A planning bucket. Lightweight grouping for a milestone, sprint, or release.
- `project` (FK)
- `name`, `description`, `status`
- `created_by`

### 6.2 `TestRun`
An actual run instance.
- `project` (FK)
- `plan` (FK, optional — nullable means standalone)
- `name`, `description`, `status`, `trigger_type`
- `started_at`, `ended_at`, `closed_at`
- **`run_kind`** — `planned` | `standalone` | `system_generated` ← key field

#### `run_kind` semantics
- `planned` — created inside a `TestPlan` (regression suite, milestone)
- `standalone` — user-created without a plan (one-off intentional run)
- `system_generated` — auto-created by `get_or_create_adhoc_run_case()` to host a one-off automation/AI execution

UI default: Test Runs workspace filters `run_kind ∈ {planned, standalone}`. Automation workspace shows all (including `system_generated`).

`run_kind` is **data hygiene**. It does NOT determine which Celery queue handles the run — that's controlled by execution layer (Layer 2 vs Layer 3). See `04-rbac-and-multi-tenancy.md`.

### 6.3 `TestRunCase`
The execution unit inside a run.
- `run` (FK)
- `test_case` (FK — for navigation)
- `test_case_revision` (FK — pinned execution truth)
- `status` — `pending` | `running` | `passed` | `failed` | `blocked` | `skipped` | `error`
- `assignment` (FK to user, optional)
- `order_index`, `attempt_count`
- **Lease fields**: `leased_at`, `leased_by`, `lease_expires_at`

#### Lease system
For future parallel dispatch — a worker calls `acquire_run_case_lease()` to claim ownership of a run-case for execution. Other workers see it leased and skip. Lease expires after a TTL if the worker dies.

#### Pinning rule
Every `TestRunCase` MUST pin both `test_case` and `test_case_revision`. The revision is what runs; the case is for the user to navigate "what test was this?" if the case has since been edited.

---

## 7. Automation (`automation` app)

### 7.1 `AutomationScript`
Runnable code for a test case.
- `test_case` (FK)
- `test_case_revision` (FK, optional — pinned to a specific revision)
- `framework` — `selenium` | `playwright`
- `language` — `python` (others future)
- `script_content` (text)
- `script_version`, `generated_by` — `human` | `ai_offline` | `ai_recording`
- `is_active` — boolean
- (Planned) `requirements` — pip-format dependencies
- (Planned) `docker_image` — custom runner image override
- (Planned) `source_repo_path`, `pinned_commit_sha` — for GitHub sync

#### Active script invariant
Only one `is_active=True` `AutomationScript` per `(test_case, framework, language)` combo. Activating one deactivates others.

### 7.2 `TestExecution`
One automation attempt.
- `test_case` (FK)
- `script` (FK to `AutomationScript`, optional)
- `run_case` (FK, optional — but always present in revision-safe history)
- `environment` (FK to `ExecutionEnvironment`, optional)
- `triggered_by` (user FK)
- `trigger_type` — `manual` | `ci_cd` | `scheduled` | `webhook` | `nightly` | `diagnostic` | `agent`
- `status` — `queued` | `running` | `paused` | `passed` | `failed` | `error` | `cancelled`
- `browser`, `platform`, `attempt_number`
- `started_at`, `ended_at`
- `selenium_session_id` — used to map session to noVNC URL
- `celery_task_id`
- `pause_requested` — checkpoint flag
- `stream_enabled` — whether to open noVNC pixel stream (default false)
- `debug_rerun` — if this is a debug rerun of a failed test

### 7.3 `TestResult`
Final persisted outcome.
- `execution` (OneToOne)
- `status`, `duration_ms`
- `total_steps`, `passed_steps`, `failed_steps`
- `error_message`, `stack_trace`
- `junit_xml`
- `video_url` (key in MinIO)
- `issues_count`
- (Future, Phase E) `ai_failure_analysis` — RCA text

### 7.4 `ExecutionStep`
Live step-by-step trace.
- `execution` (FK)
- `step_index`, `action`, `target_element`, `selector_used`, `input_value`
- `status` — `pending` | `running` | `passed` | `failed`
- `screenshot_url` (key in MinIO)
- `error_message`, `error_type`
- `started_at`, `ended_at`

### 7.5 `ExecutionCheckpoint`
Human pause/resume point.
- `execution` (FK)
- `step` (FK to `ExecutionStep`, optional)
- `checkpoint_key`, `title`, `instructions`
- `payload_json`
- `status` — `pending` | `resolved` | `expired` | `cancelled`
- `requested_at`, `resolved_at`, `resolved_by`

### 7.6 `ExecutionEnvironment`
Execution target definition (team-scoped).
- `team` (FK)
- `name`, `engine`, `browser`, `platform`
- `capabilities_json`
- `max_parallelism`, `is_active`

### 7.7 `ExecutionSchedule`
Cron-driven scheduled executions.
- `project` (FK)
- `suite` (FK, optional)
- `name`, `cron_expression`, `timezone`
- `browser`, `platform`
- `is_active`, `next_run_at`

### 7.8 `TestArtifact`
Files produced during execution. Local storage remains supported while MinIO is staged.
- `execution` (FK)
- `artifact_type` — `screenshot` | `video` | `log` | `junit_xml` | `trace`
- `storage_backend` — `minio`
- `storage_key` — MinIO object key
- `created_at`

See [`06-storage-and-streaming.md`](06-storage-and-streaming.md) for the migration plan.

---

## 8. Integrations (`integrations` app)

### 8.1 `IntegrationConfig`
Per-team or per-project integration settings.
- `team` (FK, optional)
- `project` (FK, optional)
- `provider` — `jira` | `github` | `jenkins`
- Encrypted `config_json` (provider-specific keys)

#### Provider config shapes (v1)
- Jira: `base_url`, `project_key`, `webhook_secret`
- GitHub: `org`, `repo`, `webhook_secret`
- Jenkins: `url`, `webhook_secret`

### 8.2 `RepositoryBinding`
Links a project to an external code repository.
- `project` (FK)
- `provider` — `github` (others future)
- `repo_full_name`, `default_branch`
- `created_by`

### 8.3 `WebhookEvent`
Durable record of every webhook delivery.
- `provider`, `event_type`
- `signature_status` — `verified` | `rejected`
- Raw payload (JSON), HTTP headers
- `processed_at`, `processing_status`

#### Signature rules
- GitHub: `X-Hub-Signature-256: sha256=<hmac>`
- Jira/Jenkins: `X-BIAT-Signature-256: sha256=<hmac>`
- Unsigned or mismatched signatures are stored with `signature_status='rejected'` and never trigger downstream processing.

### 8.4 `ExternalIssueLink`
Connects a Jira/GitHub issue to a project-owned object (e.g., a `TestCase`).
- `provider`, `external_id`, `external_url`
- Generic FK to `(content_type, object_id)` — links to any project-scoped record

### 8.5 `IntegrationActionLog`
Append-only audit trail of every external API call.
- `provider`, `action`, `target`
- `status` — `success` | `failure`
- `actor_user` (FK, optional)
- Truncated request/response (no large payloads in default API responses)

---

## 9. Authorization model summary

Three layers of authorization, checked in order:

1. **Organization role** (`UserProfile.organization_role`) — `platform_owner` / `org_admin` / `member`
2. **Team role** (`TeamMembership.role`) — `manager` / `member` / `viewer`
3. **Project role** (`ProjectMember.role`) — `manager` / `member` / `viewer`

`Team.manager` is **not** an authority field — it's a display pointer. Authority comes from `TeamMembership(role='manager')`.

See [`04-rbac-and-multi-tenancy.md`](04-rbac-and-multi-tenancy.md) for the full RBAC walkthrough including the multi-project workflow scenario.

---

## 10. Field-level rules and gotchas

### 10.1 Pagination
DRF returns `{ count, next, previous, results[] }` for all list endpoints. Page size default: 50.

### 10.2 Embeddings are heavy
Default API responses do not return `SpecChunk.embedding`. Explicit detail endpoints (`/specs/<id>/chunks/`) can include it on request.

### 10.3 Personal credentials never leak
`UserIntegrationCredential` is **never** returned by any serializer. Frontend can only check `has_jira_token: bool` etc.

### 10.4 Signed deliveries only
Webhook ingestion rejects missing/invalid signatures **before** storing the event. Unsigned attempts are visible only in logs.

### 10.5 List response shape
List serializers omit heavy fields:
- `TestSuiteSummarySerializer` — no nested sections, no linked specs
- `TestCaseSummarySerializer` — no `gherkin_preview`, no `version_history`, no `latest_result_status`
- Detail endpoints return the full shape

### 10.6 Approved-only run expansion
`expand_run_from_suite()` and `expand_run_from_section()` filter to `design_status=approved`. Drafts and archived cases are silently excluded.

### 10.7 Don't add `execution_mode`
`TestExecution.trigger_type` already answers "how was this triggered." Don't introduce a parallel `execution_mode` enum.

### 10.8 The active-script rule
Only one `AutomationScript` per `(test_case, framework, language)` can have `is_active=True`. Use the `activate_script()` service to switch — it handles the toggle atomically.

---

## 11. Where each model lives in code

| Concern | Path |
|---|---|
| Tenancy + RBAC | `apps/accounts/models/` |
| AI config | `apps/accounts/models/{team_ai_config,model_profile,ai_provider}.py` |
| Projects | `apps/projects/models/` |
| Specs | `apps/specs/models/` |
| Repository | `apps/testing/models/{test_suite,test_section,test_scenario,test_case,test_case_revision}.py` |
| Planning | `apps/testing/models/{test_plan,test_run,test_run_case}.py` |
| Automation runtime | `apps/automation/models/` |
| Integrations | `apps/integrations/models/` |
| Choices (enums) | `apps/<app>/models/choices.py` |

Services that mutate these models live in `apps/<app>/services/`. **Models hold relationships and invariants. Services hold workflows.** Don't put workflow logic in `Model.save()` overrides.
