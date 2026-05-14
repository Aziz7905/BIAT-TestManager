# Architecture reference

Deeper companion to `CLAUDE.md`. Read before touching a model, an RBAC rule, a Channels consumer, or anything in `infra/`.

## Apps and their roles

- **accounts** — Organization, Team, TeamMembership, UserProfile, AIProvider, **TeamAIConfig**, **ModelProfile**. SimpleJWT (access 15min / refresh 7d). Custom auth backend `EmailOrUsernameBackend` accepts email or username. API keys encrypted via `django-encrypted-model-fields` (requires `FIELD_ENCRYPTION_KEY` in `.env`).
- **projects** — Project + ProjectMember. Roles: `OWNER` / `EDITOR` / `VIEWER`. `ProjectMember.has_permission(action)` is the single arbiter — `OWNER` does everything, `EDITOR` can view/edit/create_suite/create_specification/run_tests, `VIEWER` can only view.
- **specs** — SpecificationSource (CSV/DOCX/XLSX/PDF/URL/Jira/text parsers in `services/parsers/`), SpecificationSourceRecord (per parsed row/section, `is_selected` gates promotion), Specification (1:1 from selected record), SpecChunk (pgvector HNSW index, 1024-dim, BAAI/bge-m3 local embeddings), EmbeddingModel. Chunking strategy `structure_aware_v1` (max 1400 chars, 120 overlap). MLflow tracks RAG evaluation. **Note:** Currently no filter drops "Project/System / Scope / MoSCoW Summary" metadata records — all parsed records become Specifications. That noise is known and on the Phase D backlog.
- **testing** — Canonical hierarchy. See "Canonical model hierarchy" below.
- **automation** — TestExecution (`selenium_session_id`, `stream_enabled`, `pause_requested`, `celery_task_id`), AutomationScript (with `docker_image` / `requirements` for custom runner images), ExecutionStep, ExecutionCheckpoint, TestArtifact (MinIO `storage_backend` + `storage_key`), ExecutionEnvironment, ExecutionSchedule. Runners: `python_script_runner.py`, `selenium_runner.py`, `playwright_runner.py` (premature — Phase E only), `manual_browser.py`, `execution_runner.py`. Streaming via Channels (`ws/executions/<id>/` and `…/browser-stream/`), ticket-based auth from `POST /test-executions/<pk>/stream-ticket/`.
- **ai** — Provider abstraction, LangGraph generation, browser authoring. See [ai-layer.md](ai-layer.md).
- **integrations** — Jira / GitHub / Jenkins. 7 models, HMAC webhook ingest. See "Integrations" below.

## Canonical model hierarchy

```
Organization
  └─ Team  ─┬─ TeamMembership
            ├─ TeamAIConfig  ──→ AIProvider + default ModelProfile
            └─ Project  ─┬─ ProjectMember
                         ├─ TestSuite
                         │   └─ TestSection (self-FK parent)
                         │       └─ TestScenario
                         │           └─ TestCase
                         │               └─ TestCaseRevision (M2M linked_specifications)
                         ├─ SpecificationSource
                         │   └─ SpecificationSourceRecord
                         │       └─ Specification (1:1 on selected import)
                         │           └─ SpecChunk (pgvector embedding)
                         ├─ TestPlan
                         │   └─ TestRun  ──→ TestRunCase (lease: leased_at / leased_by / attempt_count)
                         └─ ExecutionSchedule (cron)

TestCase
  └─ TestExecution (run_case FK to TestRunCase for planned runs)
      ├─ ExecutionStep
      ├─ ExecutionCheckpoint (status: PENDING / RESOLVED / EXPIRED)
      ├─ TestResult (1:1)
      └─ TestArtifact (MinIO storage_key)
```

## Field cheatsheet

Choices to memorize because they drive both backend logic and frontend rendering:

- `TestScenarioType` — HAPPY_PATH / ALTERNATIVE_FLOW / EDGE_CASE / SECURITY / PERFORMANCE / ACCESSIBILITY
- `TestScenarioPolarity` — POSITIVE / NEGATIVE
- `TestPriority` — CRITICAL / HIGH / MEDIUM / LOW
- `BusinessPriority` — MUST_HAVE / SHOULD_HAVE / COULD_HAVE / WONT_HAVE
- `TestCaseDesignStatus` — DRAFT / IN_REVIEW / APPROVED / ARCHIVED (`db_indexed`)
- `TestCaseAutomationStatus` — MANUAL / AUTOMATED / IN_PROGRESS
- `TestCaseOnFailureBehavior` — FAIL_AND_STOP / FAIL_BUT_CONTINUE
- `TestRunKind` — PLANNED / STANDALONE / SYSTEM_GENERATED (`db_indexed`)
- `TestRunTriggerType` — MANUAL / CI_CD / SCHEDULED / WEBHOOK
- `TestRunStatus` — PENDING / RUNNING / PASSED / FAILED / CANCELLED
- `TestRunCaseStatus` — PENDING / RUNNING / PASSED / FAILED / SKIPPED / ERROR / CANCELLED
- `ExecutionStatus` — QUEUED / RUNNING / PASSED / FAILED / ERROR / CANCELLED / PAUSED
- `ExecutionBrowser` — CHROMIUM / CHROME (Selenoid catalog) — adding browsers means updating `infra/selenoid/browsers.json` too
- `ExecutionPlatform` — DESKTOP (mobile not yet supported)
- `SpecificationIndexStatus` — PENDING / INDEXING / INDEXED / ERROR
- `ModelProfilePurpose` — `test_design` / `review` / `execution` / `default`

## RBAC entry points

Every mutating service must call one. Located at `apps/<app>/services/access.py`:

- `accounts.services.access` — team/org boundary checks
- `projects.services.access` — project membership (delegates to ProjectMember.has_permission)
- `testing.services.access` — `can_view_test_design_for_project`, `can_manage_test_design_for_project`, per-entity checks (`can_view_test_suite_record`, `…test_case_record`, etc.), plus queryset builders (`get_test_case_queryset_for_actor` and siblings)
- `automation.services.access` — `can_trigger_test_execution`, execution visibility filters
- `specs.services.access` — specification visibility per project

Pattern: service entry validates with `if not can_X(user, target): raise PermissionError(...)`, then proceeds. Views call services; views never call access.py directly.

## Channels routing

`apps/automation/routing.py`:

```
ws/executions/<uuid:execution_id>/                  ExecutionStreamConsumer
ws/executions/<uuid:execution_id>/browser-stream/   BrowserStreamConsumer
```

Both auth via signed ticket from `POST /test-executions/<pk>/stream-ticket/` (Django `core.signing`). Frontend swaps http→ws via `buildWebSocketUrl(ticket.websocket_path)`.

ExecutionStreamConsumer emits:
- `execution.snapshot` (initial)
- `execution.status_changed`
- `execution.step_updated`
- `execution.result_ready`
- `execution.artifact_created`
- `execution.checkpoint_requested` / `checkpoint_resolved` / `checkpoint_expired`

BrowserStreamConsumer proxies VNC frames from upstream (Selenoid noVNC for regression, MCP container websockify in planned Phase E).

The upstream URL is looked up via `apps/automation/services/browser_sessions.py::cache_browser_session_urls(execution_id, session_id)` → Redis. Selenium runs populate this from the Selenoid hub API; AI authoring is planned to populate it from a containerized MCP allocator.

## Celery topology

Three queues, three pool types — pool type matters and differs per OS:

| Queue | Workload | Pool (Linux prod) | Pool (Windows dev) | Concurrency |
|---|---|---|---|---|
| `ai_agent` | LangGraph + browser authoring (I/O-bound) | gevent | solo | 20 |
| `regression` | bulk script dispatch (Docker SDK calls) | prefork | solo | 4 |
| `interactive` | single executions, manual browser | prefork | solo | 2 |

Task routes (`CELERY_TASK_ROUTES` in `settings.py`):
- `ai.run_generation_session`, `ai.run_authoring_session` → `ai_agent`
- `automation.run_test_execution`, `automation.expire_stale_execution_checkpoints` → `regression`
- `automation.run_manual_browser_session` → `interactive`

Beat: `automation.expire_stale_execution_checkpoints` every 300s.

Workers spawn runner containers via Docker SDK. Run workers on the Docker host or in a container with `/var/run/docker.sock` mounted. Runner network must match `AUTOMATION_RUNNER_DOCKER_NETWORK` (default `biat_selenoid`).

## Infrastructure (`infra/` + `docker-compose.selenoid.yml`)

| Service | Image | Port | Purpose |
|---|---|---|---|
| selenoid | aerokube/selenoid:latest-release | 4444 | Browser hub. Mounts `/var/run/docker.sock`. `-limit 5` |
| selenoid-ui | aerokube/selenoid-ui:latest-release | 8080 | Selenoid dashboard |
| minio | minio/minio:latest | 9000 / 9001 | Artifact storage. Bucket `biat-artifacts` |
| minio-create-bucket | minio/mc:latest | — | One-shot init for the bucket |

Network: `biat_selenoid` (custom bridge). All services join it so runners can resolve `selenoid` and `minio` by hostname.

**Runner Dockerfiles** (`infra/runners/`):

- `python/Dockerfile` — `FROM python:3.13-slim`, installs `boto3 redis requests selenium>=4.25`. Tag: `biat-runner-python:latest`. **No Playwright** (Layer 3 only via MCP, not in runners).
- `java/Dockerfile` — `FROM maven:3.9-eclipse-temurin-21`. Tag: `biat-runner-java:latest`. Maven build runner.

Settings tie-in: `AUTOMATION_PYTHON_RUNNER_IMAGE`, `AUTOMATION_JAVA_RUNNER_IMAGE`, `AUTOMATION_RUNNER_DOCKER_NETWORK`, `MINIO_*`, `SELENOID_HUB_URL`, `SELENOID_PUBLIC_URL`.

## Integrations app (full, not a stub)

`apps/integrations/` ships seven models:

- **IntegrationProvider** — reference table, seeded with `jira` / `github` / `jenkins` (migration 0003).
- **IntegrationConfig** — team or team+project scoped, encrypted `config_json_encrypted` (jira base_url+project_key, github org+repo, jenkins url).
- **UserIntegrationCredential** — per-user encrypted token. Unique on `(user_profile, provider)`.
- **RepositoryBinding** — project ↔ external repo (e.g., GitHub repo). Used for webhook scoping.
- **WebhookEvent** — durable ingest log; unique on `(provider, external_id)`.
- **IntegrationActionLog** — audit trail for outbound integration calls.
- **ExternalIssueLink** — `GenericForeignKey` linking external issues to any domain object (TestCase, TestRun, etc.).

Endpoints under `/integrations/...`:
- `POST /integrations/webhooks/<provider>/` — HMAC-SHA256 verified, AllowAny, durable ingest
- Team / project / user config CRUD; repository binding CRUD; webhook event list/detail; external issue link CRUD; action log list

Services (`apps/integrations/services/`):
- `workflows.py` — `verify_webhook_signature` (HMAC-SHA256), `process_webhook_event`, `link_external_issue_to_object`
- `resolver.py` — **`resolve_integration_credentials`** with `act_as_app` (team/project config) vs `act_as_user` (user token, with optional app fallback). All integration callers (including AI agents in Phase E) must go through this seam.
- `configurations.py` — legacy Team-fields shim + config read/write

No Celery tasks; webhook handling is synchronous in the request path.

## Settings of note

Located in `src/biat_testmanager/settings.py`. Read carefully before changing.

- Database: PostgreSQL with pgvector extension. Connection from `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT`.
- JWT: 15 min access, 7 day refresh, AccessToken class only (no rotating refresh).
- Channels: Redis-backed (`channels_redis`) using `CHANNEL_REDIS_URL`.
- Celery: `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`, queues + routes + beat as above.
- Specs: `SPEC_EMBEDDING_MODEL_NAME=BAAI/bge-m3`, `SPEC_EMBEDDING_VECTOR_DIMENSIONS=1024`, `SPEC_CHUNK_STRATEGY=structure_aware_v1`, `SPEC_CHUNK_MAX_CHARS=1400`, `SPEC_CHUNK_OVERLAP_CHARS=120`.
- MLflow: `MLFLOW_TRACKING_URI=sqlite:///mlflow.db` (default), `MLFLOW_ARTIFACT_ROOT`, `MLFLOW_EXPERIMENT_NAME=biat-test-manager-specs`.
- Selenoid: `SELENOID_HUB_URL` (host side) and `SELENOID_RUNNER_HUB_URL` (runner-container side — uses `selenoid` hostname inside the network).
- MinIO: `MINIO_ENDPOINT_URL` (host) vs `MINIO_RUNNER_ENDPOINT_URL` (runner side — `http://minio:9000`).
- AI: `AI_GENERATION_ENABLE_CRITIC` (default False; see `phases.md` D.5), `AI_PLAYWRIGHT_MCP_COMMAND` (default `npx`), `AI_PLAYWRIGHT_MCP_ARGS` (default `["@playwright/mcp@latest", "--headless"]`), `AI_PLAYWRIGHT_MCP_START_TIMEOUT_SECONDS` (45), `AI_PLAYWRIGHT_MCP_CALL_TIMEOUT_SECONDS` (30), `AI_PLAYWRIGHT_MCP_LOG_FILE` (optional real file path for MCP stderr — see Celery LoggingProxy note in `ai-layer.md`).

## Frontend touch points (lives in `../../frontend/`)

Frontend is a separate app; this file only notes the seams the backend exposes for it.

- Axios client builds bearer + refresh-queue against `VITE_API_BASE_URL`. JWT expiry fires a custom `biat-auth-expired` event.
- AI generation drawer (`AIGenerationPanel.tsx`) polls `GET /ai/generations/{id}/` every 1.8s.
- AI authoring entry from `CaseWorkspacePanel.tsx` → `AIAuthoringStartModal.tsx` → `POST /ai/authoring/sessions/` → navigates to `AutomationLivePage` with the returned execution id.
- `AutomationLivePage` uses `NoVncViewer` (via `@novnc/novnc`) and an executionStore that subscribes to the ExecutionStreamConsumer. Shows "No browser session active" when `selenium_session_id` is empty — this is the gap Phase E Step 2 closes.
