# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project in one paragraph

BIAT TestManager is a self-hosted QA platform for BIAT (Banque Internationale Arabe de Tunisie). It is built as **three intentionally separate layers**: (1) test management — suites/sections/scenarios/cases with revisions and traceability; (2) Selenium regression execution — Docker runner containers against Selenoid, MinIO artifacts, Channels-based live streaming; (3) AI agent layer on top — `TeamAIConfig` + `ModelProfile` per-purpose provider abstraction, LangGraph test generation, Playwright MCP browser authoring, and (deferred) self-healing. Layers 1–2 are stable; Layer 3 is the active build. Long-term target is KaneAI-equivalent behavior tailored to bank QA.

## Hard architectural rules

These are load-bearing. Do not relitigate them without checking `docs/PLATFORM.md`.

1. **Playwright is the AI agent's interface only (Layer 3, via Playwright MCP).** Never for scripted regression — regression always uses Selenium. The runner Dockerfiles in `infra/runners/` deliberately do not include Playwright.
2. **AI generates drafts; humans approve before anything becomes canonical.** `apps/ai/services/commit_service.commit_selected_drafts` is the only path that writes canonical TestSuite/Section/Scenario/Case rows from AI output. Browser-authoring traces land as `TestCaseRevision` with `design_status=DRAFT`.
3. **Do not refactor non-AI models** (`testing`, `automation`, `specs`, `accounts`, `projects`, `integrations`). They are stable and shared. AI is built *on top*, not woven in.
4. **`HealingEvent` is deliberately removed** (see `docs/backlog.md` for the spec). It returns in Phase F, not before.
5. **Celery enqueue belongs in `transaction.on_commit(...)`** when called from any view that may eventually run inside `atomic()` — otherwise the worker can pick up a task before the row commits.

## Repo layout (this backend only)

```
Backend/biat_testmanager/
├── pyproject.toml          uv-managed deps
├── README.md               canonical setup/run instructions — keep in sync
├── docker-compose.selenoid.yml
├── docs/                   PLATFORM.md, roadmap.md, architecture/01..09, backlog.md
├── infra/                  selenoid/ + runners/{python,java}/Dockerfile
├── src/
│   ├── manage.py
│   ├── biat_testmanager/   Django project (settings, asgi, celery)
│   └── apps/
│       ├── accounts/       Org/Team/User, RBAC, TeamAIConfig, ModelProfile
│       ├── projects/       Project, ProjectMember
│       ├── specs/          SpecificationSource → Specification → SpecChunk (pgvector)
│       ├── testing/        Suite → Section → Scenario → Case → Revision; Plan → Run → RunCase
│       ├── automation/     TestExecution, AutomationScript, ExecutionStep, runners, streaming
│       ├── ai/             providers, LangGraph generation, browser authoring (Playwright MCP)
│       └── integrations/   Jira / GitHub / Jenkins (7 models, HMAC webhooks)
└── .claude/                this folder — themed reference docs for future sessions
```

## Canonical data model

```
Organization → Team → Project → TestSuite → TestSection (self-nesting)
                                          → TestScenario → TestCase → TestCaseRevision
                                          ↘ Specification (M2M linked_specifications on Case + Revision)
Project → TestPlan → TestRun → TestRunCase (lease fields: leased_at / leased_by / attempt_count)
TestCase → TestExecution → ExecutionStep / ExecutionCheckpoint / TestResult / TestArtifact
Team → TeamAIConfig → AIProvider, default ModelProfile (purpose ∈ {test_design, review, execution, default})
Project → SpecificationSource → SpecificationSourceRecord → Specification → SpecChunk (1024-dim pgvector, BAAI/bge-m3)
```

See [.claude/architecture.md](.claude/architecture.md) for fields, RBAC entry points, Channels routing, runner infra.

## Celery topology (three queues, three pool types)

- `ai_agent` — long LangGraph + browser-authoring sessions. **gevent on Linux**, `solo` on Windows.
- `regression` — bulk dispatch of saved scripts. **prefork on Linux**, `solo` on Windows.
- `interactive` — single executions, debug rerun, manual browser sessions. **prefork on Linux**, `solo` on Windows.

Task routes (in `settings.py`):
- `ai.run_generation_session`, `ai.run_authoring_session` → `ai_agent`
- `automation.run_test_execution`, `automation.expire_stale_execution_checkpoints` → `regression`
- `automation.run_manual_browser_session` → `interactive`

Beat: `automation.expire_stale_execution_checkpoints` every 300s.

Broker / result backend / Channels / browser-session-URL cache: Redis (`redis://localhost:6379/0`).

## Where business logic lives

- **All business logic in services** (`apps/<app>/services/*.py`). Views are thin DRF wrappers that call services.
- **RBAC entry points in `apps/<app>/services/access.py`.** Every mutating service should call one.
- **Canonical writes from AI output** go through `apps/ai/services/commit_service.py` only.
- **TestCase + revision pairing** via `apps/testing/services/repository.py::create_test_case_with_revision` / `update_test_case_with_revision`.

See [.claude/conventions.md](.claude/conventions.md) for full conventions.

## Common commands

Working directory matters. `uv sync` runs at `Backend/biat_testmanager/`. Django commands run from `Backend/biat_testmanager/src/` with `$env:DEBUG='true'` on Windows.

```pwsh
# Install deps (run from Backend/biat_testmanager/)
uv sync

# Migrations and checks (run from Backend/biat_testmanager/src/)
$env:DEBUG='true'
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate

# Dev server (run from Backend/biat_testmanager/src/)
uv run python manage.py runserver

# Run all tests for an app
uv run python manage.py test apps.ai --keepdb
uv run python manage.py test apps.automation --keepdb
uv run python manage.py test apps.testing --keepdb

# Run a single test class or method
uv run python manage.py test apps.ai.tests.test_browser_authoring --keepdb
uv run python manage.py test apps.ai.tests.test_generation_workflow.TestGenerationWorkflow.test_persist_ready_for_review --keepdb

# Celery worker — single-process dev shortcut (consumes all queues, one task at a time)
uv run celery -A biat_testmanager worker -Q ai_agent,regression,interactive --pool=solo -l info

# Celery worker — Linux production (split by queue with correct pool type)
uv run celery -A biat_testmanager worker -Q ai_agent    --pool=gevent  -c 20 -l info
uv run celery -A biat_testmanager worker -Q regression  --pool=prefork -c 4  -l info
uv run celery -A biat_testmanager worker -Q interactive --pool=prefork -c 2  -l info

# Playwright browsers (only needed for Phase E browser authoring)
uv run playwright install chromium

# Selenoid + MinIO infra
docker compose -f docker-compose.selenoid.yml up -d

# Redis (one option)
docker run --name biat-redis -p 6379:6379 -d redis:7
```

See [.claude/commands.md](.claude/commands.md) for the full command reference (env vars, runner image build, MLflow, embedding reindex).

## Phase status (as of this writing)

- **Phase 1–2 (test management + Selenium regression):** stable, do not refactor.
- **Phase D (AI test design quality):** designed in plan, not yet implemented. Six steps: per-requirement-group fan-out, stronger extraction, coverage expansion, coverage map, optional critic, diversity enforcement.
- **Phase E (Playwright MCP browser authoring):** foundation in place; live VNC viewer not yet wired (MCP runs `--headless`, `get_stream_session_id` returns None). Three known follow-up steps in the plan.
- **Phase F (self-healing):** deferred. Full spec in `docs/backlog.md`.

See [.claude/phases.md](.claude/phases.md) for the per-step plan and [.claude/ai-layer.md](.claude/ai-layer.md) for the AI app deep dive.

## Authoritative docs (read these before deep work)

- `docs/PLATFORM.md` — master spec, three-layer rules
- `docs/roadmap.md` — official build order with step numbering
- `docs/architecture/02-three-layer-architecture.md` — layer separation
- `docs/architecture/05-execution-engine.md` — Celery queues, runner architecture, `__BIAT_EVENT__` stdout protocol
- `docs/architecture/07-ai-layer.md` — AI config model and phases
- `docs/architecture/08-integrations.md` — Jira / GitHub / Jenkins, HMAC, strict vs lax mode
- `docs/architecture/09-specs-and-rag.md` — pgvector + BAAI/bge-m3 chunking
- `docs/backlog.md` — `HealingEvent` spec for Phase F
- `../../frontend/docs/architecture/05-ai-ux.md` — agent launcher modal, narration timeline event vocabulary, healing review queue

## Known stale notes in this repo

- `README.md` lists five apps (omits `ai` and `integrations`) — both exist and are non-trivial.
- `README.md` still references `HealingEvent` as future-facing schema — the model was removed; see `docs/backlog.md`.
