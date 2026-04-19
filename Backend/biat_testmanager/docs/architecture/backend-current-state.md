# BIAT TestManager Backend Current State

This document summarizes the backend architecture completed through Batch 7.

The current goal is a strong non-AI QA platform first. AI, LangGraph, and MCP should remain optional layers added later on top of stable domain records.

## Core Rules

- The platform must be useful without AI.
- Views stay thin.
- Serializers validate and map data only.
- Workflow/business logic belongs in services.
- Models hold relationships, constraints, and simple invariants.
- Design-time data, revisions, execution data, integrations, and audit logs stay separated.
- Avoid dangling raw UUID references to future systems. Add real foreign keys only when the target app exists.

## Batch 1 - Tenancy And RBAC

Completed:

- `Organization` owns teams and users.
- `Team` belongs to one organization.
- `UserProfile.organization_role` is the organization-level role.
- `TeamMembership` is the source of truth for team-level roles.
- `ProjectMember` is the project-level permission layer.
- `primary_team` remains UI/default context only; it does not grant authority.
- Access checks follow this order:
  1. platform/org role
  2. team membership
  3. project membership

Important result:

- `Team.manager` is no longer the authority source. Manager authority comes from `TeamMembership(role="manager")`.

## Batch 2 - AI And Integration Configuration Extraction

Completed:

- AI configuration moved away from `Team` into:
  - `TeamAIConfig`
  - `ModelProfile`
- Integration configuration moved away from `Team` / `UserProfile` into:
  - `IntegrationConfig`
  - `UserIntegrationCredential`
- Compatibility helpers still expose legacy Jira/GitHub/Jenkins/AI fields where needed.

Important result:

- Teams can later support cloud and local AI providers without changing test repository or execution models.
- Personal integration credentials are separate from shared team/project integration configuration.

## Batch 3 - Specs And Retrieval

Completed:

- Specification ingestion and retrieval were hardened around:
  - `SpecificationSource`
  - `SpecificationSourceRecord`
  - `Specification`
  - `SpecChunk`
  - `EmbeddingModel`
- `BAAI/bge-m3` is the current embedding baseline.
- Indexing is treated as an explicit service flow, not hidden serializer work.
- Heavy retrieval artifacts such as embeddings should not be returned by default API responses.

Important result:

- Specs can support test design, traceability, and later AI grounding without making AI mandatory.

## Batch 4 - Test Repository Model

Completed:

- Repository hierarchy:
  - `TestSuite`
  - `TestSection`
  - `TestScenario`
  - `TestCase`
  - `TestCaseRevision`
- Test case authoring state is separated from execution result state.
- `TestCaseRevision` stores immutable snapshots of revision-worthy fields.
- Traceability links can connect specs to live cases and revisions.
- Pass rate methods should aggregate from execution results, not mutable case design status.

Important result:

- A test run can always point to the exact case revision that existed when execution started.

## Batch 5 - Plans, Runs, And Revision-Safe Execution

Completed:

- Added execution planning layer:
  - `TestPlan`
  - `TestRun`
  - `TestRunCase`
- `TestRunCase` pins:
  - `TestCase`
  - `TestCaseRevision`
- `TestExecution` now links to `TestRunCase`.
- Old direct one-off execution paths can auto-create a lightweight run and run-case.

Important result:

- Execution history is run-scoped and revision-safe.
- Future parallel execution can dispatch individual `TestRunCase` records.

## Batch 6 - Automation Engine Contracts

Completed:

- Added:
  - `ExecutionEnvironment`
  - `TestArtifact`
- `AutomationScript` can target a fixed `TestCaseRevision`.
- `TestExecution` acts as a runtime attempt under `TestRunCase`.
- `TestRunCase` has minimal lease/attempt fields for later dispatch.
- Playwright and Selenium share one engine contract.
- Artifacts are stored as child records instead of a single result path.

Important result:

- The backend is ready to grow toward local workers, containers, Selenium Grid, or cloud execution without changing core test/run models.

Not complete yet:

- Full container orchestration.
- Cloud browser/device provider integration.
- KaneAI-style interactive execution.

Those are future execution-polish features, not Batch 6 base schema work.

## Batch 7 - Integrations Foundation

Completed:

- Existing:
  - `IntegrationConfig`
  - `UserIntegrationCredential`
- Added:
  - `RepositoryBinding`
  - `WebhookEvent`
  - `ExternalIssueLink`
  - `IntegrationActionLog`
- Added integration workflow services for:
  - configuring team integration settings
  - configuring project integration overrides
  - storing acting-as-user credentials
  - binding a project to a repository
  - ingesting webhooks durably
  - linking external issues to project-owned objects
  - recording external action audit logs
- Added thin integration APIs and admin registrations.

Important result:

- Jira, GitHub, and Jenkins can be modeled as normal non-AI product integrations.
- Webhooks and external actions are durable and auditable.
- Webhook ingestion now requires signed HMAC-SHA256 delivery headers before storing events.
- MCP and LangGraph can later use this layer, but they do not replace it.

## Batch 7.1 - Non-AI Hardening

Completed:

- Global DRF pagination is enabled with a default page size of 50.
- Integration list endpoints keep heavy payloads out of default list responses.
- Webhook ingestion rejects missing, invalid, or unmatched signatures.
- Integration config and credential updates use safer upsert-style writes.
- Optional MLflow/embedding telemetry failures are logged instead of silently swallowed.
- Celery execution fallback is allowed for development/eager mode only; production enqueue failures raise loudly.

## Phase 6.1 - Specs Cleanup

Completed:

- The legacy Groq test-design demo endpoints remain registered only as compatibility endpoints.
- `test-design-preview` and `test-design-apply` now return a stable `410 Gone` response.
- Those legacy endpoints no longer call Groq and no longer create suites, scenarios, or test cases.
- The old Groq generation serializer and service modules have been removed from active code.
- Non-AI specification workflows remain active:
  - create and list specification sources
  - parse sources into records
  - review and update source records
  - import selected records into specifications
  - list/detail specifications
  - index specifications with the current `BAAI/bge-m3` retrieval baseline

Important result:

- AI-assisted generation is intentionally deferred to the future reviewed generation workspace.
- The current specs app is a non-AI requirements and retrieval layer, not a direct AI-writing layer.

## Phase 6.2 - Accounts Cleanup

Completed:

- `UserProfile.role`, `UserProfile.team`, and `UserProfile.team_id` remain compatibility shims only.
- Account authorization continues to read:
  1. `UserProfile.organization_role`
  2. `TeamMembership.role`
  3. `ProjectMember.role`
- Team membership creation no longer derives a new membership role from the target user's legacy profile role.
- Adding a user who manages another team now defaults to a viewer membership unless the actor explicitly requests another allowed role.
- `Team.manager` is documented and displayed in admin as a legacy assignment pointer, while membership managers are shown separately.
- Platform-owner deletion protection now checks `organization_role` directly instead of the legacy `role` property.

Important result:

- Legacy account API fields still work for current clients, but new business logic no longer treats compatibility fields as authority.

## Phase 6.3 - Projects Cleanup

Completed:

- Project creation, detail updates, archive/restore, member add, member role update, and member removal now have explicit workflow services.
- Existing project/member endpoints remain compatible, but serializers now delegate business actions to the project service layer.
- Project archive/restore are explicit use-case endpoints instead of relying only on generic update/delete behavior.
- Project list queries annotate member counts and reuse prefetched members for summary fields.
- Project admin now uses explicit related-object loading and read-only audit timestamps.

Important result:

- Projects now follow the same backend direction as the rest of the platform: views are thin, serializers validate/map, and business actions live in services.

## Current High-Level Model

```text
Organization
  -> Team
    -> TeamMembership
    -> Project
      -> ProjectMember
      -> Specification
        -> SpecChunk
      -> TestSuite
        -> TestSection
          -> TestScenario
            -> TestCase
              -> TestCaseRevision
      -> TestPlan
        -> TestRun
          -> TestRunCase
            -> TestExecution
              -> TestResult
              -> ExecutionStep
              -> TestArtifact
      -> RepositoryBinding
      -> WebhookEvent
      -> ExternalIssueLink
      -> IntegrationActionLog

Team
  -> TeamAIConfig
    -> ModelProfile
  -> IntegrationConfig

UserProfile
  -> UserIntegrationCredential
```

## What The Platform Can Do Now

- Manage organizations, teams, users, and project membership.
- Store project specifications and retrieval chunks.
- Build a structured test repository.
- Preserve immutable test case revisions.
- Create test plans and test runs.
- Expand runs into revision-safe run cases.
- Execute automated scripts through a shared Playwright/Selenium contract.
- Watch executions live over WebSocket with execution-scoped stream tickets.
- Pause on human-required checkpoints and resume them through an explicit API workflow.
- Store execution results and artifacts.
- Store Jira/GitHub/Jenkins configuration and credentials.
- Bind projects to repositories.
- Store webhook deliveries.
- Link external issues to project-owned objects.
- Audit external integration actions.

## Phase 6.4 - Testing Cleanup

Completed:

- Suite, section, and scenario creation now go through explicit service functions in `services/repository.py`:
  - `create_test_suite` (also creates default section)
  - `create_test_section`
  - `create_test_scenario`
- Scenario cloning moved from `TestScenario.clone()` on the model into `clone_test_scenario()` service function.
- Design-status transition service functions added: `approve_test_case`, `archive_test_case`.
- Design-status workflow endpoints added:
  - `POST /test-cases/{id}/approve/` â€” transitions to approved
  - `POST /test-cases/{id}/archive/` â€” transitions to archived
- `TestSuiteSerializer` split into three serializers:
  - `TestSuiteWriteSerializer` â€” write operations only
  - `TestSuiteSummarySerializer` â€” list responses (no nested sections, no heavy linked specs traversal)
  - `TestSuiteSerializer` â€” detail responses only (full nested shape)
- `TestCaseSummarySerializer` added for list responses â€” excludes `gherkin_preview`, `version_history`, and `latest_result_status` (which previously caused N+1 queries on list views).
- Views updated to use summary serializers on list, detail serializers on detail, write serializers on create/update.
- Redundant double permission checks removed from views â€” `perform_update` and `perform_destroy` are used instead of overriding `update`/`destroy` directly.
- Run expansion (`expand_run_from_suite`, `expand_run_from_section`) now filters to `design_status=approved` only. Draft and archived cases are excluded from runs.
- Admin hardened across all testing models:
  - `list_select_related` enabled on all admin classes
  - `raw_id_fields` added for FK fields
  - `TestCaseRevision` admin is fully read-only with `has_add_permission` and `has_change_permission` blocked
  - `TestPlan`, `TestRun`, `TestRunCase` now registered in admin
- Groq-era test files removed: `test_generation_templates.py`, `test_source_test_design_generation_api.py`.
- `test_traceability_api.py` updated to use `organization_role` instead of legacy `role` field.
- `test_batch5_runs.py` updated to create cases with `design_status=APPROVED` so expansion tests remain valid under the new filter.
- New test file `test_phase64_testing.py` covers: service functions, clone, approve/archive services, approve/archive API endpoints, expansion filter behavior, list vs detail serializer shapes.
- `services/__init__.py` cleaned up â€” Groq-era generation template exports removed.

Important results:

- List responses for suites no longer traverse the full sectionâ†’scenarioâ†’case tree on every request.
- Test cases cannot be added to runs unless they are explicitly approved â€” enforces the designâ†’reviewâ†’approve workflow.
- The testing app now follows the same backend direction as accounts and projects: thin views, validate/map serializers, business logic in services.

## Phase 6.5 - Automation Cleanup

Completed:

- `activate_script` and `deactivate_script` service functions added to `services/execution_runner.py` and exported from `services/__init__.py`. Views no longer do `script.is_active = True/False; script.save()` inline.
- `AutomationScriptActivateView` and `DeactivateView` now delegate to the service functions.
- `ExecutionScheduleTriggerView` now calls `trigger_execution_schedule(schedule)` directly from the service instead of `schedule.trigger_now()` (a model method).
- Redundant double permission checks removed from `AutomationScriptDetailView`, `TestExecutionDetailView`, and `ExecutionScheduleDetailView` â€” `perform_update` and `perform_destroy` used instead of overriding `update`/`destroy`.
- Redundant `can_view_test_execution_record` checks removed from `TestResultDetailView.get_object()` and `TestResultExportJunitView.get()` â€” queryset scoping is the sole guard.
- `ai_failure_analysis` removed from `TestResultSerializer.Meta.fields` â€” AI-era field no longer exposed in API responses.
- `TestResult.analyze_failure()` dead method removed.
- `HealingEvent` model deleted (AI-era self-healing selector recovery â€” never populated by any runner code). Migration `0005_remove_healing_event` drops the table.
- `HealingDetectionMethod` and `HealingEventStatus` choice classes removed from `choices.py`.
- Admin hardened across all automation models: `list_select_related = True`, `raw_id_fields` for all FK columns, `readonly_fields` for audit timestamps. `ExecutionEnvironment` and `TestArtifact` now registered.
- Legacy `UserProfileRole` usage replaced with `OrganizationRole.MEMBER` + `TeamMembership` in `test_automation_api.py`, `test_automation_services.py`, and `test_batch6_execution.py`.
- `test_batch6_execution.py` test cases that feed run-expansion updated to `design_status=APPROVED` so the expansion filter does not exclude them.
- New test file `test_phase65_automation.py` covers: `activate_script`/`deactivate_script` service correctness, `TestResultSerializer` does not expose `ai_failure_analysis`, activate/deactivate API endpoints (viewer forbidden, unauthenticated forbidden), schedule trigger response shape.

Important results:

- The automation app now follows the same backend direction as accounts, projects, and testing: views are thin, model mutations go through service functions, queryset scoping is the sole permission guard on retrieve.
- AI-era dead infrastructure (self-healing) removed without breaking migrations â€” one clean migration documents the removal.

## Dead Code Sweep + UserProfileRole Removal

Completed after Phase 6.5:

- Two orphan wrapper functions (`map_profile_role_to_membership_role`, `map_membership_role_to_profile_role`) removed from `services/memberships.py` â€” never called.
- `TestExecution.stream_logs()` removed â€” defined but never called by any runner.
- `UserProfileRole` fully deleted: the class, the 3 mapping functions (`map_legacy_role_to_organization_role`, `map_legacy_role_to_membership_role`, `map_membership_role_to_legacy_role`), the `UserProfile.__init__` compatibility shim, and the `UserProfile.role` property/setter.
- `get_effective_user_role()` in `services/roles.py` now returns native `TeamMembershipRole` and `OrganizationRole` values instead of legacy strings.
- `AdminCreateUserSerializer` and `AdminUpdateUserSerializer` now accept `team_membership_role` (a `TeamMembershipRole` value) instead of the legacy `role` field. The `_resolve_requested_roles` bridge function removed.
- `role` removed from `UserProfileSerializer` and `MyProfileSerializer` â€” `organization_role` is the canonical field, team-level role is in `team_memberships[].role`.
- `ProjectMemberSerializer.user_role` now reads `organization_role` instead of the removed `role` shim.
- `UserProfileAdmin.resolved_role` display column removed from the admin list.
- All test files updated to use `organization_role=OrganizationRole.MEMBER` and `TeamMembershipRole` directly.

## Phase 6.6 - Live Execution Streaming V1

Completed:

- Added Django Channels with Redis-backed channel layers for normal app runs and in-memory channel layers during Django test runs.
- Added signed execution stream tickets:
  - `POST /api/test-executions/{id}/stream-ticket/`
  - short-lived Django-signed payload with salt `execution-stream-ticket`
  - ticket TTL is 120 seconds
- Added WebSocket execution stream endpoint:
  - `ws/executions/{execution_id}/?ticket=...`
- Added `ExecutionCheckpoint` as a durable execution-scoped record for human-required pauses.
- Added checkpoint resume API:
  - `POST /api/test-executions/{execution_id}/checkpoints/{checkpoint_id}/resume/`
- Added Python runtime helper API for Playwright/Selenium subprocess scripts:
  - `report_step_started(...)`
  - `report_step_passed(...)`
  - `report_step_failed(...)`
  - `artifact_created(...)`
  - `require_human_action(...)`
- Added reserved subprocess event wire format:
  - `__BIAT_EVENT__<json>`
- Added execution control-file contract under the canonical artifact directory:
  - `<artifact_dir>/control/checkpoint-<checkpoint_key>.resume.json`
  - `<artifact_dir>/control/execution.stop`
- Live runner event parsing now creates or updates `ExecutionStep`, `TestArtifact`, and `ExecutionCheckpoint` rows as events arrive.
- WebSocket consumers now publish:
  - execution snapshots
  - execution status changes
  - step updates
  - checkpoint requested/resolved/expired events
  - artifact-created events
  - final result-ready events
- Added Celery task and beat schedule for expiring stale checkpoints older than 60 minutes.
- Scripts with no runtime helper events remain backward compatible and still fall back to prebuilt steps from the linked test case.

Hardening pass (post-review):

- `publish_execution_event()` now treats WebSocket publish as best-effort — channel layer failures are caught and swallowed so Redis going down never crashes an in-flight execution.
- `_load_snapshot` in the consumer now uses `select_related("result")` to avoid a hidden extra DB query on every WebSocket connection.
- Dead code branch in `_upsert_execution_step` removed.
- Expired-ticket path added to `test_live_execution_streaming.py`.

Important result:

- The backend now supports a real non-AI live execution experience: users can watch an execution in real time, handle manual checkpoints such as login/MFA, resume safely, and keep execution history tied to durable execution, step, artifact, and checkpoint records.

Still deferred:

- Full browser takeover / remote attachable sessions
- Container orchestration and cloud browser providers
- AI-guided execution, healing, or agent-driven interaction

## Phase 6.7 - Reporting And Dashboard Layer

Completed:

- Added project-scoped reporting query services in the `testing` app for:
  - dashboard overview summary cards
  - recent run cards
  - pass-rate trend over time
  - failure hotspots
- Added thin reporting endpoints:
  - `GET /api/projects/<project_id>/reporting/overview/`
  - `GET /api/projects/<project_id>/reporting/pass-rate-trend/`
  - `GET /api/projects/<project_id>/reporting/failure-hotspots/`
- Reporting stays use-case based:
  - the overview endpoint returns summary cards plus recent runs
  - the trend endpoint returns chart-ready daily pass-rate points
  - the hotspots endpoint returns the most failure-prone test cases for a recent window
- Existing `GET /api/test-runs/?project=<id>` remains the full run-history endpoint for project run lists.

Important result:

- The backend can now power non-AI dashboards directly from stable run, run-case, execution, and result records without forcing the frontend to stitch together low-level CRUD endpoints.

## What Comes Next

Confirmed order:

1. **Thin frontend** - built on top of the stabilized repository, execution streaming, and reporting APIs.
2. **Execution UX polish** - richer operator workflows around live execution, result inspection, and later browser/session control.
3. **AI design workspace** - use `TeamAIConfig` + `ModelProfile` to call the configured provider (Ollama etc.) for test case generation from specs.
4. **LangGraph / MCP agent layer** - autonomous agents on top of the finished non-AI core.

## Non-AI Product First

The next product target should be a polished non-AI platform:

- manage specs
- design test cases
- version test assets
- plan runs
- run Playwright/Selenium automation
- stream execution state
- inspect results and artifacts
- link Jira/GitHub/Jenkins context
- view dashboards

After that, AI can be layered on top for generation, review, healing, and code/spec analysis without forcing a base-model rewrite.
