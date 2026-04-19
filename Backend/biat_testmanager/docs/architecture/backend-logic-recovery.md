# Backend Logic Recovery

Last updated: 2026-04-19

This file is a compact recovery note for the current backend mental model so we do not have to rebuild it from context every time.

## 1. Core split

The backend currently has 3 connected layers:

1. Repository and design data
2. Planning and execution tracking
3. Automation runtime and result persistence

The important rule is:

- `TestCase` is the live editable design record.
- `TestCaseRevision` is the frozen snapshot used to preserve execution truth.
- `TestRunCase` pins a specific case revision inside a run.
- `TestExecution` is one automation attempt against a case and usually against a run-case.
- `TestResult` is the persisted final outcome of that execution.

## 2. Main testing models

### `TestCase`

Holds the live design:

- title
- preconditions
- structured `steps`
- expected_result
- test_data
- design_status
- automation_status
- `on_failure`
- `timeout_ms`
- version
- linked specifications

Design-changing edits should go through repository services so revisions stay correct.

### `TestCaseRevision`

Frozen case snapshot:

- belongs to one `TestCase`
- stores title, preconditions, steps, expected result, test data
- stores linked specifications at that moment
- stores source snapshot metadata
- increments `version_number`

This is the execution-safe design truth.

### `TestPlan`

Planning bucket for a project:

- project
- name
- description
- status
- created_by

It is lightweight right now. Good for grouping runs, not yet a full milestone/release system.

### `TestRun`

Actual run instance:

- optional link to `TestPlan`
- project
- name
- status
- trigger_type
- started_at / ended_at

It derives pass rate from its run-cases.

### `TestRunCase`

Bridge between design and execution:

- belongs to one run
- points to `test_case` for navigation
- points to `test_case_revision` for pinned execution truth
- status
- assignment
- order_index
- attempt_count
- lease fields: `leased_at`, `leased_by`

This is the unit that should matter most in run execution UI.

## 3. Repository service rules

Repository services live in `apps.testing.services.repository`.

Key behaviors:

- `create_test_suite(...)` creates the suite and ensures a default root section
- `create_test_section(...)` supports nesting via `parent`
- `create_test_scenario(...)` supports `business_priority`
- `create_test_case_with_revision(...)` creates a case and its first revision
- `update_test_case_with_revision(...)` updates the case and writes a new revision only when revision fields or linked specs changed
- `clone_test_scenario(...)` clones a scenario and all of its cases
- `clone_test_case(...)` clones a case into the same scenario with a fresh revision history

Important current rule:

- not every field change creates a revision
- revision logic is tied mainly to design content and linked specifications

## 4. Run service rules

Run services live in `apps.testing.services.runs`.

Key behaviors:

- `create_test_plan(...)`
- `archive_test_plan(...)`
- `create_test_run(...)`
- `start_test_run(...)`
- `close_test_run(...)`
- `expand_run_from_cases(...)`
- `expand_run_from_section(...)`
- `expand_run_from_suite(...)`
- `get_or_create_adhoc_run_case(...)`
- `acquire_run_case_lease(...)`
- `release_run_case_lease(...)`
- `sync_run_case_status_from_execution(...)`

Important current rules:

- expanding a run pins the latest available `TestCaseRevision`
- suite/section expansion includes only approved cases
- direct case execution still creates or reuses an ad-hoc run-case so executions remain revision-safe
- execution outcome syncs back into `TestRunCase`
- run final status is derived from run-case statuses

## 5. Automation models

Automation lives in `apps.automation`.

### `AutomationScript`

Stores runnable code for a case:

- belongs to one `TestCase`
- may be pinned to a specific `TestCaseRevision`
- framework
- language
- script_content
- script_version
- generated_by
- is_active

Current rule:

- only one active script per case/framework/language combo

### `TestExecution`

One automation attempt:

- test_case
- optional script
- optional run_case
- optional execution environment
- triggered_by
- trigger_type
- status
- browser
- platform
- attempt_number
- started_at / ended_at

This is the runtime record.

### `TestResult`

Final persisted outcome of an execution:

- execution
- status
- duration_ms
- total_steps
- passed_steps
- failed_steps
- error_message
- stack_trace
- junit_xml
- video_url
- ai_failure_analysis
- issues_count

### `ExecutionStep`

Runtime step-by-step trace:

- execution
- step_index
- action
- target_element
- selector_used
- input_value
- screenshot_url
- status
- error details
- timing

### `ExecutionCheckpoint`

Human pause/resume checkpoint in a live execution:

- execution
- optional step
- checkpoint_key
- title
- instructions
- payload_json
- status
- requested_at / resolved_at / resolved_by

### `ExecutionEnvironment`

Execution target definition:

- team
- name
- engine
- browser
- platform
- capabilities_json
- max_parallelism
- is_active

### `ExecutionSchedule`

Scheduled execution definition:

- project
- optional suite
- name
- cron_expression
- timezone
- browser
- platform
- is_active
- next_run_at

## 6. Execution flow

Main runtime logic lives in `apps.automation.services.execution_runner`.

Flow:

1. User or system requests execution.
2. `create_execution_record(...)` selects the best script.
3. If no run-case was supplied, `get_or_create_adhoc_run_case(...)` creates one.
4. Environment is resolved from team + engine + browser + platform.
5. `TestExecution` is created with status `queued`.
6. Task is queued through Celery, with eager fallback in debug/eager mode.
7. Worker runs `run_execution(execution_id)`.
8. Worker acquires the run-case lease and marks the execution as running.
9. Engine is selected from script framework or environment engine.
10. Engine runs and produces status, error info, and artifacts.
11. `finalize_execution_result(...)` writes `TestResult`.
12. Execution status is mapped back to `TestRunCase`.
13. Run may auto-close based on run-case terminal states.
14. Lease is released.

## 7. Engine abstraction

Execution engines live behind a shared contract in `apps.automation.services.engine`.

Current state:

- Playwright path is the real primary path
- Selenium path exists behind the same interface but is still secondary/stub-like compared to Playwright

This matches current product direction:

- E2E / UI first
- Playwright native
- API/performance/security later via ingestion or future extensions

## 8. API surface already present

Testing app already exposes:

- plan CRUD
- run CRUD
- run start / close / expand
- run-case list/detail

Automation app already exposes:

- automation script CRUD
- activate / deactivate / validate script
- execution create/list/detail
- pause / resume / stop execution
- execution stream ticket
- checkpoint resume
- execution steps list/detail
- result detail
- JUnit export
- execution schedules and trigger-now behavior

## 9. Product gaps that still matter

Current backend is more capable than the frontend surface.

Main gaps:

- specs and traceability UI are still not properly exposed
- runs and execution UI are still underexposed
- automation runtime exists in backend, but frontend interaction around it is still thin
- reporting/dashboard should be driven by real run/result usage after the above is surfaced

## 10. Practical next work order

Recommended order:

1. Finish repository UX polish
2. Expose linked specifications and traceability UI
3. Expose run and execution screens using existing backend
4. Improve reporting/dashboard once real execution data is flowing
5. Add AI-generated case review flows later without breaking the repository IA

## 11. One-line summary

The backend already has the real skeleton of a serious test manager:

- repository design with revisions
- planning and run tracking with pinned revisions
- automation scripts and executions
- result persistence and run status sync

The next big value is not new core models. It is exposing this backend well in the frontend.
