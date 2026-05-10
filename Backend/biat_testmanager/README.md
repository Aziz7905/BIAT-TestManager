# BIAT Test Manager Backend

This backend powers the BIAT Test Manager platform: authentication, project access, specification ingestion, manual test design, requirement traceability, and automation execution.

## Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- pgvector
- Celery
- Redis
- MLflow
- Docker
- Selenoid
- MinIO

## Backend Apps

- `accounts`: organizations, teams, memberships, user profile
- `projects`: project model and project membership
- `specs`: source ingestion, normalized specifications, chunks, embeddings
- `testing`: suites, scenarios, test cases, traceability
- `automation`: scripts, executions, steps, results, schedules

## Current Execution Model

The execution layer is a self-hosted browser E2E pipeline backed by Selenoid, Docker runner containers, Celery, Redis, and MinIO.

- `AutomationScript` stores runnable scripts
- `TestExecution` stores run lifecycle and history
- `ExecutionStep` stores step-level progress
- `TestResult` stores final outcome and artifacts metadata
- `ExecutionSchedule` is persisted for future scheduling support
- `HealingEvent` exists as future-facing schema only

Current v1 rule:

- Selenium Python and Selenium Java scripts run in Docker runner containers against Selenoid
- Browser pixel streaming is opt-in through `stream_enabled`
- Artifacts are stored by `storage_backend` + `storage_key`, with MinIO as the active backend

## Directory Layout

```text
Backend/biat_testmanager/
├─ pyproject.toml
├─ .env
├─ src/
│  ├─ manage.py
│  ├─ biat_testmanager/
│  ├─ media/
│  └─ apps/
│     ├─ accounts/
│     ├─ automation/
│     ├─ projects/
│     ├─ specs/
│     └─ testing/
└─ mlruns/
```

## Requirements

- Python version compatible with the project `pyproject.toml`
- PostgreSQL running locally
- Redis running locally

## Environment Variables

Create a `.env` file in `Backend/biat_testmanager/` with values appropriate for your machine.

Typical variables used by the project:

```env
SECRET_KEY=replace-me
FIELD_ENCRYPTION_KEY=replace-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=replace-me
DB_USER=replace-me
DB_PASSWORD=replace-me
DB_HOST=localhost
DB_PORT=5432

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

SELENOID_HUB_URL=http://localhost:4444/wd/hub
SELENOID_RUNNER_HUB_URL=http://selenoid:4444/wd/hub
SELENOID_PUBLIC_URL=http://localhost:4444
AUTOMATION_RUNNER_DOCKER_NETWORK=biat_selenoid
MINIO_ENDPOINT_URL=http://localhost:9000
MINIO_RUNNER_ENDPOINT_URL=http://minio:9000
MINIO_ACCESS_KEY=biat
MINIO_SECRET_KEY=biat-secret
MINIO_BUCKET_NAME=biat-artifacts

SPEC_EMBEDDING_MODEL_NAME=replace-me
SPEC_EMBEDDING_LOCAL_FILES_ONLY=True

MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_ARTIFACT_ROOT=file:///absolute/path/to/mlruns
MLFLOW_EXPERIMENT_NAME=biat-test-manager-specs
```

Do not commit real secrets or local machine-specific absolute paths.

## Install Dependencies

From `Backend/biat_testmanager`:

```powershell
uv sync
```

## Run Migrations

From `Backend/biat_testmanager/src`:

```powershell
$env:DEBUG='true'
uv run python manage.py migrate
```

## Start the Django Server

From `Backend/biat_testmanager/src`:

```powershell
$env:DEBUG='true'
uv run python manage.py runserver
```

The API is typically available at `http://127.0.0.1:8000/`.

## Start Redis

One simple local option is Docker:

```powershell
docker run --name biat-redis -p 6379:6379 -d redis:7
```

If the container already exists:

```powershell
docker start biat-redis
```

## Start Celery

The platform uses **three queues**, one per workload:

- `ai_agent` — long-lived LangGraph sessions (Phase E, planned)
- `regression` — bulk dispatch of saved scripts from planned/standalone runs
- `interactive` — single executions, debug rerun, manual browser sessions

From `Backend/biat_testmanager/src`:

**Linux production** — one worker process per queue with the right pool:

```bash
uv run celery -A biat_testmanager worker -Q ai_agent    --pool=gevent  -c 20 -l info
uv run celery -A biat_testmanager worker -Q regression  --pool=prefork -c 4  -l info
uv run celery -A biat_testmanager worker -Q interactive --pool=prefork -c 2  -l info
```

The `ai_agent` queue uses **gevent** because agent loops are I/O-bound (LLM calls + browser actions); one process serves up to 20 concurrent sessions. The `regression` and `interactive` queues use **prefork** because they coordinate Docker runner containers.

### Docker socket access

Execution workers spawn Java/Python runner containers through the Docker SDK. In the current single-host setup, run the Celery workers on the Docker host, or run them in a container with `/var/run/docker.sock` mounted. Keep `AUTOMATION_RUNNER_DOCKER_NETWORK=biat_selenoid` unless your Docker Compose network uses a different name; the later Moon/K8s migration removes this direct Docker socket constraint.

**Windows development** — `prefork` is unreliable on Windows; use `solo`:

```powershell
uv run celery -A biat_testmanager worker -Q ai_agent    --pool=solo -l info
uv run celery -A biat_testmanager worker -Q regression  --pool=solo -l info
uv run celery -A biat_testmanager worker -Q interactive --pool=solo -l info
```

For a single-worker dev shortcut (consumes all three queues, one task at a time):

```powershell
uv run celery -A biat_testmanager worker -Q ai_agent,regression,interactive --pool=solo -l info
```

## Playwright Setup

Install browser binaries locally if needed:

```powershell
uv run playwright install chromium
```

## Checks and Tests

From `Backend/biat_testmanager/src`:

```powershell
$env:DEBUG='true'
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test apps.automation.tests
```

## API Notes

Main API domains include:

- authentication and user access
- project management
- specifications and source ingestion
- test suites, scenarios, and cases
- automation scripts and executions

Swagger or DRF docs availability depends on your local URL config and environment.

## Current Backend Scope

What is solid now:

- manual-first QA domain model
- specification normalization
- requirement-to-test traceability
- automation execution storage model
- Celery-backed execution pipeline

What is still evolving:

- richer execution UX
- full scheduling orchestration
- cloud execution/device farm support
- self-healing behavior
- AI orchestration on top of the manual-first product
