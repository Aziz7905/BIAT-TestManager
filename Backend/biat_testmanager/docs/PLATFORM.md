# BIAT TestManager — Backend Documentation

**Last updated:** 2026-05-08
**Status:** Single source of truth for the backend platform

---

## What this document is

This is the **master document** for the BIAT TestManager backend. Read this first. It explains:

1. What we are building (and what we are deliberately not building)
2. The high-level architecture in three layers
3. Where to find detailed documentation for each subsystem
4. The current build state and the next steps

If you only have time for one document, read this one. Then drill into `architecture/` for the specifics of any layer.

---

## 1. The product in one paragraph

BIAT TestManager is a self-hosted AI-native QA platform for a Tunisian bank (BIAT). It combines three things in one product:
- a TestRail-style **test management** layer (specs, plans, runs, cases, results)
- a small **regression execution engine** (Selenium scripts dispatched to Selenoid through Docker runner containers)
- a **KaneAI-equivalent AI agent** (LangGraph + Playwright MCP, running in Selenoid containers, that explores apps, generates tests from Jira tickets and GitHub PRs, drives a browser live, and self-heals broken selectors)

The platform is bank-scale and on-premise. It is **not** trying to be LambdaTest's HyperExecute — no 3000+ browsers, no device farms, no global cloud. It is trying to be the smallest correct version of KaneAI that a single engineering team can build and run inside a bank's network.

### Product scope boundary

The near-term owned execution path is **browser E2E testing**. BIAT can deeply author, run, debug, and report Selenium browser regressions inside its own infrastructure.

Other test types — performance, security, API, unit, integration, and future mobile automation — can still exist in the platform as managed test assets and ingested results, but BIAT is **not** building native runtime infrastructure for them in this phase. Jenkins, GitHub Actions, a bank-owned lab, or another existing tool can run those tests; BIAT consumes their outputs through the Results Ingest API and gives teams one place to plan, trace, review, and report.

For bank-facing Selenium browser work, the default runner target should be **Java**. Python remains useful for development, prototypes, and existing scripts, but Java runner support is part of making the platform realistic for teams whose automation stack is already Java.

---

## 2. The three-layer architecture

The platform is **three layers stacked**. Each layer is independently useful. Each one is buildable on top of the layer below it.

```
┌───────────────────────────────────────────────────────────────────┐
│  Layer 3 — AI Agent (the KaneAI equivalent)                       │
│                                                                   │
│  LangGraph agent driving Playwright via MCP                       │
│    • Reads Jira tickets → generates E2E test cases                │
│    • Reads GitHub PR diffs → selects/generates regression tests   │
│    • Explores the app live → records actions                      │
│    • Translates recordings → Selenium Java/Python script          │
│    • Self-heals broken selectors                                  │
│    • Posts RCA + results back to GitHub PRs / Jira issues         │
│                                                                   │
│  Browser: Selenoid (one isolated container per session)           │
│  Live view: noVNC stream, ALWAYS on for agent sessions            │
│  Queue: ai_agent (long-lived, gevent pool)                        │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  Layer 2 — Regression + Single Execution (HyperExecute lite)      │
│                                                                   │
│  Celery workers dispatch Selenium scripts to Selenoid             │
│  Scripts come from one of three sources:                          │
│    • Engineer wrote them in the in-platform code editor           │
│    • Engineer pushed them to GitHub → platform syncs              │
│    • AI agent generated them (Layer 3) → reviewed → approved      │
│                                                                   │
│  Browser: Selenoid (one isolated container per execution)         │
│  Live view: noVNC OFF by default — opt-in via debug rerun         │
│             or "Watch this run". Saved video at end is enough.    │
│  Queues:                                                          │
│    • regression — bulk dispatch from planned/standalone runs      │
│    • interactive — single test execution / debug rerun /          │
│                    manual browser session                         │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  Hybrid path — Results Ingest API                                 │
│                                                                   │
│  External execution (engineer's IDE, Jenkins, GitHub Actions)     │
│  POSTs JUnit XML / structured payload to the platform.            │
│  Same TestExecution + TestResult rows are populated.              │
│  Reporting and pass-rate work identically across both paths.      │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  Layer 1 — Test Management (the TestRail equivalent)              │
│                                                                   │
│  Plans → Runs → RunCases → Results                                │
│  Specs (PDF/DOCX/XLSX/CSV/URL/Jira) → Specifications → SpecChunks │
│  TestSuite → TestSection → TestScenario → TestCase                │
│    └── TestCaseRevision (immutable execution-truth snapshot)      │
│  Reporting (pass-rate trends, failure hotspots)                   │
│                                                                   │
│  No browser. No execution. Purely organizational data.            │
│  This layer must be useful even if Layers 2 and 3 are turned off. │
└───────────────────────────────────────────────────────────────────┘
```

The product philosophy is strict: **the non-AI core must be stable and complete first.** AI sits on top. AI never bypasses the canonical models.

---

## 3. Stack

### Core
- **Python**, **Django 4.2**, **Django REST Framework**
- **PostgreSQL** + **pgvector** (specification embeddings)
- **Celery** + **Redis** (task queue, channel layer, control signals)
- **Django Channels** + **Daphne** (WebSocket execution streaming)

### Execution infrastructure
- **Selenoid** (Aerokube — isolated Docker browser containers) — single browser backend for Layers 2 and 3
- **Docker runner containers** — language-specific script execution isolation (planned): Java Selenium runner for bank/enterprise E2E, Python runner for dev/prototypes and existing scripts
- **MinIO** (S3-compatible self-hosted object storage) — artifacts (planned)
- **Moon** (Aerokube K8s-native) — future migration target when single-host capacity is exhausted

### AI / RAG
- **HuggingFace `BAAI/bge-m3`** (1024-dim local embedding model) — specification retrieval
- **MLflow** (embedding telemetry)
- **LangGraph** (AI agent orchestration) — planned, Layer 3
- **Playwright MCP** (agent's browser interface) — planned, Layer 3
- **TeamAIConfig + ModelProfile + AIProvider** (already wired, no provider call yet)

### Frontend (separate documentation)
- See `frontend/docs/PLATFORM.md`

---

## 4. Apps

| App | Responsibility |
|---|---|
| `accounts` | Organization, Team, TeamMembership, UserProfile, ProjectMember, AI/integration config (`TeamAIConfig`, `ModelProfile`, `AIProvider`), user credentials |
| `projects` | Project model, project membership, archive/restore |
| `specs` | `SpecificationSource`, `SpecificationSourceRecord`, `Specification`, `SpecChunk`, `EmbeddingModel`. CSV/DOCX/XLSX/PDF/URL/Jira parsers. pgvector RAG indexing with MLflow telemetry |
| `testing` | Repository (`TestSuite` → `TestSection` → `TestScenario` → `TestCase` → `TestCaseRevision`), planning (`TestPlan`, `TestRun`, `TestRunCase`), reporting endpoints |
| `automation` | `AutomationScript`, `TestExecution`, `ExecutionStep`, `TestResult`, `TestArtifact`, `ExecutionCheckpoint`, `ExecutionEnvironment`, `ExecutionSchedule`. Selenoid + Docker runners. WebSocket streaming. Manual browser sessions |
| `integrations` | `IntegrationConfig`, `UserIntegrationCredential`, `RepositoryBinding`, `WebhookEvent`, `ExternalIssueLink`, `IntegrationActionLog`. HMAC-signed Jira / GitHub / Jenkins webhooks |

---

## 5. Where to find the details

This master document is intentionally short. The detailed documentation lives in `architecture/`:

| Document | What it covers |
|---|---|
| [`architecture/01-product-vision.md`](architecture/01-product-vision.md) | What we are building, the KaneAI comparison, what we deliberately are not building |
| [`architecture/02-three-layer-architecture.md`](architecture/02-three-layer-architecture.md) | Detailed walkthrough of the three layers, what flows between them, why the separation matters |
| [`architecture/03-domain-model.md`](architecture/03-domain-model.md) | All models, relationships, invariants. The canonical data hierarchy. `run_kind`, `TestCaseRevision`, the lease system |
| [`architecture/04-rbac-and-multi-tenancy.md`](architecture/04-rbac-and-multi-tenancy.md) | The 3-layer authorization model, multi-tenant isolation, concurrency groups (per-project quotas), the team workflow scenario |
| [`architecture/05-execution-engine.md`](architecture/05-execution-engine.md) | The Celery queues, Selenoid, Docker runner containers, the `__BIAT_EVENT__` protocol, checkpoint resume |
| [`architecture/06-storage-and-streaming.md`](architecture/06-storage-and-streaming.md) | MinIO for artifacts, when to stream live (and when not to), debug rerun mode, video recording strategy |
| [`architecture/07-ai-layer.md`](architecture/07-ai-layer.md) | `TeamAIConfig`, API key management, Ollama deployment, Phase D (offline generation), Phase E (live agent), Phase F (self-healing), AI RCA |
| [`architecture/08-integrations.md`](architecture/08-integrations.md) | GitHub source-of-truth sync, Jira ticket → test generation, webhook ingestion, HMAC signatures, action audit |
| [`architecture/09-specs-and-rag.md`](architecture/09-specs-and-rag.md) | Specification ingestion, parsers, chunking, pgvector retrieval, the RAG layer that grounds AI generation |

Plus two top-level documents:

| Document | What it covers |
|---|---|
| [`roadmap.md`](roadmap.md) | The build order. What is done, what is next, in what sequence and why |
| [`backlog.md`](backlog.md) | Decisions that were intentionally deferred (e.g., self-healing). Not forgotten — explicitly waiting |

---

## 6. The canonical domain hierarchy

```
Organization
  └─ Team ── TeamAIConfig ── ModelProfile ── AIProvider
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
            │   └─ TestRun (run_kind: planned | standalone | system_generated)
            │       └─ TestRunCase  ←── pins (TestCase, TestCaseRevision)
            │             └─ TestExecution
            │                   ├─ TestResult
            │                   ├─ ExecutionStep
            │                   ├─ TestArtifact (in MinIO)
            │                   └─ ExecutionCheckpoint
            ├─ RepositoryBinding
            ├─ WebhookEvent
            ├─ ExternalIssueLink
            └─ IntegrationActionLog

UserProfile ── UserIntegrationCredential
```

### Key invariants (don't relitigate these)
- `TestCase` is **live editable design**. `TestCaseRevision` is the **immutable snapshot** used by execution.
- `TestRunCase` always pins both `TestCase` (for navigation) and `TestCaseRevision` (for execution truth).
- `TestExecution` is one runtime attempt. It links to `TestRunCase`.
- Suite/section run expansion includes only `design_status=approved` cases.
- Only one `is_active=True` `AutomationScript` per (case, framework, language) combo.
- AI never bypasses canonical models — it produces **reviewed candidates** that become real records.

---

## 7. The hard rules

These are the rules we don't relitigate. They have been decided. Each rule has a reason.

1. **The platform must be useful without AI.** Layer 1 stands alone.
2. **Hybrid execution path.** Tests can run on the platform (Celery → Selenoid) OR externally (engineer's IDE / Jenkins / GitHub Actions) and ingest results via the Results Ingest API. Both populate the same `TestExecution` rows.
3. **Selenium scripts are the firm's deterministic execution engine.** Layer 2 only. Never AI-driven at runtime.
4. **Playwright = AI agent's interface.** Layer 3 only, via Playwright MCP. Never used for scripted regression runs.
5. **AI generates reviewed candidates.** A human approves before anything becomes a canonical `TestCase` or `AutomationScript`.
6. **Views thin · Serializers validate/map · Services hold business logic · Models hold relationships and invariants.**
7. **Don't add `execution_mode` enum** — `trigger_type` already answers "how was this executed".
8. **AI API keys live server-side, never user-facing.** `TeamAIConfig` holds them. Individual users never see or configure keys.
9. **Three Celery queues, one per workload.** `ai_agent` (gevent, long-lived sessions), `regression` (prefork, bulk dispatch), `interactive` (prefork, single executions / debug rerun). `run_kind` is data hygiene; queue choice is workload-driven.
10. **Live noVNC streams are always-on for AI agent sessions and opt-in for regression / interactive.** Nobody watches 1000 silent regression runs live; saved video at the end is enough.
11. **Artifacts go to MinIO, not the local filesystem.** Database stores keys, not blobs.
12. **Single source of truth per concern.** AI config lives in `TeamAIConfig` only (not `Team`). `IntegrationProvider` is the canonical provider catalog. App-level integration config lives in `IntegrationConfig` only (not `Team`). User-owned credentials live in `UserIntegrationCredential` only (not `UserProfile`).
13. **Integration callers use resolvers, never read fields directly.** `IntegrationResolverService` returns the right credentials for `act_as_user` vs `act_as_app` modes; AI agents must go through it too.
14. **Native execution is browser E2E first.** Performance, security, API, unit, and integration tests are managed and ingested, not executed by first-party BIAT infrastructure in the current scope.
15. **Regression execution is not a CI replacement.** Jenkins/GitHub Actions/other bank infrastructure can still own scheduling and non-browser engines; BIAT provides management, traceability, reporting, AI authoring, and one native browser E2E execution lane.

---

## 8. The current build state in one paragraph

Layer 1 (test management) is **complete and stable**: tenancy, RBAC, project membership, specs + pgvector RAG, repository with revisions, plans/runs/run-cases, reporting, and integration foundation. Layer 2 (browser E2E regression execution) is being moved onto the target MVP infrastructure: Celery queues, Selenoid browser sessions, Docker Java/Python runners, MinIO artifact keys, WebSocket events, checkpoint control, and opt-in browser streaming. The Results Ingest API for external CI/IDE/lab results is not built yet. Layer 3 (AI browser E2E authoring) is **not started** beyond configuration models: `TeamAIConfig`, `ModelProfile`, and `AIProvider` are wired, but no LLM/LangGraph/Playwright MCP loop exists yet. See [`roadmap.md`](roadmap.md) for the full step-by-step plan to close the gap.

---

## 9. Local runtime

```
1. PostgreSQL (with pgvector extension)
2. Redis (docker run --name biat-redis -p 6379:6379 -d redis:7)
3. Selenoid + MinIO (docker compose -f docker-compose.selenoid.yml up)
4. Selenoid (planned, not running yet)
5. MinIO (planned, not running yet)
6. uv run python manage.py migrate
7. uv run python manage.py runserver
8. uv run celery -A biat_testmanager worker -l info --pool=solo   # solo on Windows
9. Frontend: npm run dev
```

`.env` variables of note: `DB_*`, `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `CELERY_BROKER_URL`, `SPEC_EMBEDDING_MODEL_NAME`, `SPEC_EMBEDDING_LOCAL_FILES_ONLY`, `MLFLOW_TRACKING_URI`, `SELENOID_HUB_URL`, `SELENOID_RUNNER_HUB_URL`, `SELENOID_PUBLIC_URL`, `MINIO_ENDPOINT_URL`, `MINIO_RUNNER_ENDPOINT_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`.

---

## 10. Where to look in code

| Concern | Path |
|---|---|
| Domain models | `apps/<app>/models/` |
| Business logic | `apps/<app>/services/` |
| Engine + runners | `apps/automation/services/{engine,selenium_runner,playwright_runner,python_script_runner}.py` |
| Live streaming | `apps/automation/consumers.py`, `services/streaming.py`, `runtime.py` |
| Browser integration | `apps/automation/services/{browser_sessions,manual_browser}.py` |
| Spec retrieval | `apps/specs/services/{chunking,embeddings,indexing}.py` |
| Run lifecycle | `apps/testing/services/runs.py` |
| Repository operations | `apps/testing/services/repository.py` |
| Celery tasks | `apps/automation/tasks.py` |
| Celery config | `biat_testmanager/celery.py`, settings under `CELERY_*` |
| WebSocket routing | `apps/automation/routing.py`, `biat_testmanager/asgi.py` |
| Settings | `biat_testmanager/settings.py` |

---

## 11. Reading order for someone new to the project

1. **This document** — get the big picture in 10 minutes
2. [`architecture/01-product-vision.md`](architecture/01-product-vision.md) — understand the KaneAI comparison and what we're building
3. [`architecture/02-three-layer-architecture.md`](architecture/02-three-layer-architecture.md) — internalize the layer separation
4. [`architecture/03-domain-model.md`](architecture/03-domain-model.md) — learn the data model and invariants
5. [`architecture/04-rbac-and-multi-tenancy.md`](architecture/04-rbac-and-multi-tenancy.md) — understand how teams use the platform
6. [`architecture/05-execution-engine.md`](architecture/05-execution-engine.md) — understand how scripts actually run
7. [`roadmap.md`](roadmap.md) — see what's next

The other architecture documents are reference material — read them when you touch the relevant subsystem.
