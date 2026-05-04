# BIAT TestManager — Backend Documentation

**Last updated:** 2026-04-26
**Scope:** What the backend is right now. Single source of truth. All other backend `.md` files are historical batch notes; read this first.

---

## 1. Product in one paragraph

BIAT TestManager is a self-hosted QA platform for a Tunisian bank (BIAT). It manages requirements (specifications), structured test design (suites → scenarios → cases with revisions), planning (plans → runs → run-cases), automation (Selenium / Playwright scripts run via Celery + Redis), live execution streaming (Django Channels + WebSockets + noVNC), and reporting. AI is **not** part of the core today — it is a deliberately deferred top layer.

---

## 2. Stack

- **Python**, **Django 4.2**, **Django REST Framework**
- **PostgreSQL** + **pgvector** (for spec embedding retrieval)
- **Celery** + **Redis** (task queue + channel layer)
- **Django Channels** + **Daphne** (WebSocket execution streaming)
- **MLflow** (embedding telemetry)
- **Selenium Grid** (Docker Compose: Hub + 3 Chrome nodes, noVNC on 7900/7901/7902)
- **Playwright** (Python, secondary engine)
- **HuggingFace `BAAI/bge-m3`** (local embedding model under `HuggingFace_models/`)

---

## 3. Apps

| App | Responsibility |
|---|---|
| `accounts` | Organization, Team, TeamMembership, UserProfile, ProjectMember, AI/integration config (`TeamAIConfig`, `ModelProfile`), user credentials |
| `projects` | Project model + project membership |
| `specs` | `SpecificationSource`, `SpecificationSourceRecord`, `Specification`, `SpecChunk`, `EmbeddingModel`. CSV/DOCX/XLSX/PDF/URL/Jira parsers. pgvector RAG indexing with MLflow telemetry |
| `testing` | Repository (`TestSuite` → `TestSection` → `TestScenario` → `TestCase` → `TestCaseRevision`), planning (`TestPlan`, `TestRun`, `TestRunCase`), reporting endpoints |
| `automation` | `AutomationScript`, `TestExecution`, `ExecutionStep`, `TestResult`, `TestArtifact`, `ExecutionCheckpoint`, `ExecutionEnvironment`, `ExecutionSchedule`. Selenium Grid + Playwright runners. WebSocket streaming. Manual browser sessions |
| `integrations` | `IntegrationConfig`, `UserIntegrationCredential`, `RepositoryBinding`, `WebhookEvent`, `ExternalIssueLink`, `IntegrationActionLog`. Jira / GitHub / Jenkins HMAC-signed webhooks |

---

## 4. Domain model (the canonical chain)

```
Organization
  └─ Team ── TeamAIConfig ── ModelProfile
       │   └─ IntegrationConfig
       └─ Project
            ├─ ProjectMember
            ├─ Specification ── SpecChunk (pgvector)
            │     └─ SpecificationSource ── SpecificationSourceRecord
            ├─ TestSuite
            │   └─ TestSection
            │       └─ TestScenario
            │           └─ TestCase ── TestCaseRevision (immutable snapshots)
            │                 └─ AutomationScript (pinned to revision)
            ├─ TestPlan
            │   └─ TestRun
            │       └─ TestRunCase  ←── pins (TestCase, TestCaseRevision)
            │             └─ TestExecution
            │                   ├─ TestResult
            │                   ├─ ExecutionStep
            │                   ├─ TestArtifact
            │                   └─ ExecutionCheckpoint
            ├─ RepositoryBinding
            ├─ WebhookEvent
            ├─ ExternalIssueLink
            └─ IntegrationActionLog

UserProfile ── UserIntegrationCredential
```

### Key invariants

- `TestCase` is **live editable design**. `TestCaseRevision` is the **immutable snapshot** used by execution.
- `TestRunCase` always pins both `TestCase` (for navigation) and `TestCaseRevision` (for execution truth).
- `TestExecution` is one runtime attempt. It links to `TestRunCase` (optional but always present for revision-safe history).
- Suite/section run expansion includes only `design_status=approved` cases.
- Only one `is_active=True` `AutomationScript` per (case, framework, language) combo.

---

## 5. Authorization model

Three layers, checked in this order:

1. **Platform / Organization role** — `UserProfile.organization_role` (`platform_owner` / `org_admin` / `member`)
2. **Team-level role** — `TeamMembership.role` (`manager` / `member` / `viewer`)
3. **Project-level role** — `ProjectMember.role`

Legacy fields (`UserProfile.role`, `Team.manager` as authority) have been removed. `Team.manager` exists only as a display pointer.

---

## 6. Specs and retrieval

- **Sources:** files (PDF, DOCX, XLSX, CSV) or URLs / Jira links → parsed into `SpecificationSourceRecord` rows for human review.
- **Imported records** become canonical `Specification` rows.
- **`SpecChunk`** holds chunked content with a 1024-dim pgvector embedding from `BAAI/bge-m3` (HNSW cosine index).
- **Indexing service** (`apps.specs.services.indexing`) is explicit, MLflow-tracked, and idempotent. Default response payloads do **not** return embeddings.
- Chunking is sentence-window with overlap (`SPEC_CHUNK_MAX_CHARS=1400`, `SPEC_CHUNK_OVERLAP_CHARS=120`).

---

## 7. Automation runtime

### Engine contract (`apps.automation.services.engine`)
Both Playwright and Selenium implement the same interface. Engine selected from script framework first, environment engine second.

### Selenium Grid (current focus)
- `docker-compose.selenium-grid.yml` — Hub on `:4444`, 3 Chrome nodes with noVNC on `:7900-7902`.
- Scripts receive `BIAT_SELENIUM_GRID_URL` env var → use `RemoteWebDriver`.
- `apps.automation.services.grid` maps a Selenium `session_id` to its node's noVNC WebSocket URL.

### Execution flow (happy path)
1. User triggers execution → `create_execution_record(...)` selects best active script.
2. `get_or_create_adhoc_run_case(...)` ensures a revision-safe `TestRunCase` exists if none was passed.
3. `TestExecution` created with status `queued` → enqueued to Celery (eager fallback in DEBUG only).
4. Worker (`run_execution`) acquires the run-case lease, sets execution to `running`.
5. Engine launches the script as a subprocess. Script can emit `__BIAT_EVENT__<json>` events:
   - `report_step_started / passed / failed`
   - `artifact_created`
   - `require_human_action` (creates an `ExecutionCheckpoint`, pauses worker)
6. Backend persists those events as `ExecutionStep`, `TestArtifact`, `ExecutionCheckpoint` rows and re-broadcasts them on the WebSocket.
7. `finalize_execution_result(...)` writes `TestResult`. Status syncs back to `TestRunCase`. Run auto-closes when all cases are terminal.

### Live streaming (Phase 6.6)
- `POST /api/test-executions/{id}/stream-ticket/` — short-lived signed ticket (TTL 120s).
- `ws/executions/{execution_id}/?ticket=...` — execution event stream (snapshot + status, step, artifact, checkpoint, result events).
- Browser pixel stream proxied through a Channels consumer to the Grid node noVNC WebSocket.
- Channel layer: Redis in normal runs, in-memory during Django tests.

### Checkpoint resume
- `POST /api/test-executions/{execution_id}/checkpoints/{checkpoint_id}/resume/`
- Filesystem control file: `<artifact_dir>/control/checkpoint-<key>.resume.json`
- Stop signal: `<artifact_dir>/control/execution.stop`
- *(Filesystem coupling is a known limitation — moves to Redis pub/sub when execution moves into containers.)*

### Manual browser sessions (`services/manual_browser.py`)
Diagnostic browser sessions outside an execution — used by the test-case "Open browser" button. Same Grid + VNC streaming infrastructure.

### Celery beat
- `automation.expire_stale_execution_checkpoints` every 5 min.

---

## 8. Run vs Execution semantics (TestRail-style two-track model)

Today **all `TestRun` rows are stored in one table**, and ad-hoc auto-created runs are inferred from name + null plan. Direction agreed for cleanup:

- Add **`TestRun.run_kind`** with values: `planned | standalone | system_generated`.
  - `planned` — created inside a `TestPlan` (regression / milestone).
  - `standalone` — user-created without a plan (one-off intentional run).
  - `system_generated` — auto-created by `get_or_create_adhoc_run_case()` to host a one-off automation/AI execution.
- **Keep `TestExecution.trigger_type` as-is** (`manual / ci_cd / scheduled / webhook / nightly / diagnostic`). Do **not** add an `execution_mode` enum — it duplicates `trigger_type`.
- UI: Test Runs workspace filters `run_kind ∈ {planned, standalone}` by default. Automation workspace shows all (including `system_generated`) so executions stay traceable.

This is the only schema change planned for the run/execution split. Not yet shipped.

---

## 9. Reporting (Phase 6.7)

Project-scoped read endpoints on top of execution history:

- `GET /api/projects/<id>/reporting/overview/` — summary cards + recent runs.
- `GET /api/projects/<id>/reporting/pass-rate-trend/` — daily chart points.
- `GET /api/projects/<id>/reporting/failure-hotspots/` — most failure-prone cases.

`GET /api/test-runs/?project=<id>` remains the full run-history endpoint.

---

## 10. Integrations

- Encrypted JSON config per team (Jira / GitHub / Jenkins). Project-level overrides supported.
- Webhooks **require HMAC-SHA256** (`X-Hub-Signature-256` for GitHub, `X-BIAT-Signature-256` for Jira/Jenkins). Unsigned / mismatched deliveries are rejected.
- `ExternalIssueLink` connects Jira/GitHub issues to project domain objects.
- `IntegrationActionLog` — append-only audit of external operations.
- Personal credentials (`UserIntegrationCredential`) are never returned by API.

---

## 11. API surface (high-level)

### Auth / Accounts
- `POST /api/login/`, `/logout/`, `/refresh/`, `GET /api/me/`
- `GET/PATCH /api/profile/`, `POST /api/profile/change-password/`
- `GET/POST/PATCH/DELETE /api/admin/users/`
- `GET/POST/PATCH/DELETE /api/teams/[/<id>/members/]`

### Projects
- `GET/POST/PATCH/DELETE /api/projects/`
- `GET /api/projects/:id/tree/`
- `GET/POST/PATCH/DELETE /api/projects/:id/members/`
- Archive / restore endpoints

### Specs
- Source CRUD + parse + import
- Specification list / detail / index / chunk retrieval

### Testing (repository + planning)
- Suites / sections / scenarios / cases CRUD (with revision-aware update)
- `POST /test-cases/{id}/approve/`, `/archive/`
- Plans CRUD; runs CRUD; `start_test_run`, `close_test_run`
- Run expansion (from cases / section / suite — approved only)
- Run-case list / detail
- Reporting (overview / trend / hotspots)

### Automation
- Automation script CRUD + `activate` / `deactivate` / `validate`
- Test execution create / list / detail
- `pause` / `resume` / `stop`
- Stream ticket + WebSocket execution stream
- Checkpoint resume
- Execution steps list / detail
- Result detail + JUnit XML export
- Execution schedules + `trigger-now`
- Manual browser session (open / close)

### Integrations
- Team / project integration config CRUD
- Repository bindings
- Webhook ingestion endpoints
- External issue link CRUD
- Action log read

---

## 12. What works today vs what doesn't

### ✅ Solid and stable
- Tenancy, RBAC, project membership
- Spec ingestion + pgvector retrieval
- Repository with revisions
- Plans / runs / run-cases (revision-safe)
- Automation script storage + activation
- Celery execution pipeline (Playwright Python + Selenium Grid)
- Live WebSocket telemetry (steps, artifacts, checkpoints, result)
- noVNC browser streaming during execution
- Manual checkpoint pause/resume
- Reporting endpoints
- Webhook-signed integrations layer

### 🟡 In progress
- Selenium Grid wiring (containers running; control.py + artifacts.py still filesystem-coupled — needs Redis pub/sub + shared volume)
- `selenium_session_id` field on `TestExecution` (used by Grid → noVNC URL mapping)
- `TestRun.run_kind` field — designed, not migrated

### ❌ Deferred
- AI test generation (Phase D — `TeamAIConfig` + `ModelProfile` are wired but call no provider yet)
- LangGraph + Playwright MCP agent (Phase E)
- Self-healing (`HealingEvent` was removed in Phase 6.5; spec for return is in `docs/backlog.md`)
- Distributed parallel dispatch (model supports it via `TestRunCase` lease — orchestrator not yet built)
- Cloud / device-farm execution

---

## 13. Build order from here

1. **Selenium Grid finish** — fix control + artifacts to work across containers; verify session-id → noVNC mapping.
2. **`run_kind` migration** — add field, default existing rows to `planned` if `plan_id` set else `standalone`, ad-hoc auto-creation paths set `system_generated`.
3. **Frontend execution UX completion** — see frontend `PLATFORM.md`.
4. **Reporting frontend** — surface the existing endpoints.
5. **Phase D — AI test generation** (offline): LLM via `TeamAIConfig` reads spec → returns structured `TestCase` + `AutomationScript`. Reviewed candidates before commit.
6. **Phase E — Live AI agent** (LangGraph + Playwright MCP). Agent drives Playwright live, records actions, translates to Selenium script, saves as `AutomationScript`. Uses `ExecutionCheckpoint` for human escalation.
7. **Phase F — Self-healing** per `docs/backlog.md`.

---

## 14. Hard rules (don't relitigate)

- The platform must be useful **without AI**.
- Views thin · Serializers validate/map · Services hold business logic · Models hold relationships and invariants.
- Selenium = firm's test execution engine. Playwright = AI agent's interface only (Phase E onward, never for scripted runs).
- AI generation produces **reviewed candidates** that become real `TestCase` / `AutomationScript` records. AI never bypasses canonical models.
- Don't add `execution_mode` enum — `trigger_type` already answers "how was this executed".

---

## 15. Local runtime

```
1. PostgreSQL (with pgvector extension)
2. Redis (docker run --name biat-redis -p 6379:6379 -d redis:7)
3. Selenium Grid (docker compose -f docker-compose.selenium-grid.yml up)
4. uv run python manage.py migrate
5. uv run python manage.py runserver
6. uv run celery -A biat_testmanager worker -l info --pool=solo   # solo on Windows
7. Frontend: npm run dev
```

`.env` variables of note: `DB_*`, `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `CELERY_BROKER_URL`, `SPEC_EMBEDDING_MODEL_NAME`, `SPEC_EMBEDDING_LOCAL_FILES_ONLY`, `MLFLOW_TRACKING_URI`, `SELENIUM_GRID_HUB_URL`.

---

## 16. Where to look in code

| Concern | Path |
|---|---|
| Domain models | `apps/<app>/models/` |
| Business logic | `apps/<app>/services/` |
| Engine + runners | `apps/automation/services/{engine,selenium_runner,playwright_runner,python_script_runner}.py` |
| Live streaming | `apps/automation/consumers.py`, `services/streaming.py`, `runtime.py` |
| Grid integration | `apps/automation/services/{grid,manual_browser}.py` |
| Spec retrieval | `apps/specs/services/{chunking,embeddings,indexing}.py` |
| Run lifecycle | `apps/testing/services/runs.py` |
| Repository operations | `apps/testing/services/repository.py` |
| WebSocket routing | `apps/automation/routing.py`, `biat_testmanager/asgi.py` |
| Settings | `biat_testmanager/settings.py` |
