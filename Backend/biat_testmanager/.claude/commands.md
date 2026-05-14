# Command reference

All commands verified against `README.md` and the current `pyproject.toml`. PowerShell syntax (Windows dev); Linux production variants noted where they differ.

## Working directories

- `Backend/biat_testmanager/` — `uv sync`, anything that reads `pyproject.toml`, `docker compose -f docker-compose.selenoid.yml ...`
- `Backend/biat_testmanager/src/` — every `manage.py` and `celery` command
- `frontend/` — `npm` / `npx` commands

PowerShell sets env vars per-shell:
```pwsh
$env:DEBUG = 'true'
$env:DJANGO_SETTINGS_MODULE = 'biat_testmanager.settings'  # usually inferred
```

## Installation

```pwsh
# From Backend/biat_testmanager/
uv sync

# Playwright browsers (only needed if running Phase E browser authoring locally)
uv run playwright install chromium
```

## Django

```pwsh
# From Backend/biat_testmanager/src/
$env:DEBUG = 'true'

# Sanity check (configuration, app loading, migration parity)
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run

# Apply migrations
uv run python manage.py migrate

# Create a new migration after model changes
uv run python manage.py makemigrations <app_label>

# Run the dev server (Daphne via runserver — Channels works)
uv run python manage.py runserver

# Open a shell with project models loaded
uv run python manage.py shell

# Superuser for /admin/
uv run python manage.py createsuperuser
```

## Tests

```pwsh
# From Backend/biat_testmanager/src/
$env:DEBUG = 'true'

# All tests in an app
uv run python manage.py test apps.ai --keepdb
uv run python manage.py test apps.automation --keepdb
uv run python manage.py test apps.testing --keepdb
uv run python manage.py test apps.specs --keepdb

# A specific test module
uv run python manage.py test apps.ai.tests.test_browser_authoring --keepdb
uv run python manage.py test apps.ai.tests.test_generation_workflow --keepdb
uv run python manage.py test apps.ai.tests.test_provider_and_draft_quality --keepdb

# A specific test class
uv run python manage.py test apps.ai.tests.test_generation_workflow.TestGenerationWorkflow --keepdb

# A single test method
uv run python manage.py test apps.ai.tests.test_generation_workflow.TestGenerationWorkflow.test_persist_ready_for_review --keepdb

# Drop `--keepdb` to force a full re-create of the test DB (slow; needed after migrations change)
uv run python manage.py test apps.ai
```

## Celery

Three queues, three pool types. Pool type differs per OS — `prefork` is unreliable on Windows.

```pwsh
# From Backend/biat_testmanager/src/

# Windows dev — single worker consuming all three queues, one task at a time
uv run celery -A biat_testmanager worker -Q ai_agent,regression,interactive --pool=solo -l info

# Windows dev — per-queue (still solo)
uv run celery -A biat_testmanager worker -Q ai_agent    --pool=solo -l info
uv run celery -A biat_testmanager worker -Q regression  --pool=solo -l info
uv run celery -A biat_testmanager worker -Q interactive --pool=solo -l info
```

Linux production (split by queue with the right pool):

```bash
uv run celery -A biat_testmanager worker -Q ai_agent    --pool=gevent  -c 20 -l info
uv run celery -A biat_testmanager worker -Q regression  --pool=prefork -c 4  -l info
uv run celery -A biat_testmanager worker -Q interactive --pool=prefork -c 2  -l info

# Beat (the periodic task: expire stale execution checkpoints every 300s)
uv run celery -A biat_testmanager beat -l info
```

`ai_agent` uses **gevent** because agent loops are I/O-bound (LLM + browser). `regression` and `interactive` use **prefork** because they coordinate Docker runner containers via the Docker SDK.

Workers must have Docker socket access (run on the Docker host, or in a container with `/var/run/docker.sock` mounted). The runner network is `AUTOMATION_RUNNER_DOCKER_NETWORK=biat_selenoid` by default.

## Redis

```pwsh
# Simplest local option
docker run --name biat-redis -p 6379:6379 -d redis:7

# Existing container
docker start biat-redis
```

## Selenoid + MinIO

```pwsh
# From Backend/biat_testmanager/
docker compose -f docker-compose.selenoid.yml up -d

# Health checks
# Selenoid hub:        http://localhost:4444/status
# Selenoid UI:         http://localhost:8080
# MinIO console:       http://localhost:9001  (user/pass: biat / biat-secret)
```

## Runner Docker images (build once)

```pwsh
# From Backend/biat_testmanager/
docker build -t biat-runner-python:latest -f infra/runners/python/Dockerfile infra/runners/python/
docker build -t biat-runner-java:latest   -f infra/runners/java/Dockerfile   infra/runners/java/
```

Tags must match `settings.AUTOMATION_PYTHON_RUNNER_IMAGE` and `AUTOMATION_JAVA_RUNNER_IMAGE`.

## Specs / RAG management

```pwsh
# From Backend/biat_testmanager/src/
$env:DEBUG = 'true'

# Reindex embeddings (uses BAAI/bge-m3 — first run downloads the model unless SPEC_EMBEDDING_LOCAL_FILES_ONLY=True)
uv run python manage.py reindex_spec_embeddings

# Evaluate retrieval quality (MLflow-tracked)
uv run python manage.py evaluate_spec_retrieval
```

## Frontend

```pwsh
# From frontend/
npm install

# Dev server (Vite, with HMR)
npm run dev

# Type-check only (CI-friendly, no emit)
npx tsc -b --pretty false

# Production build
npm run build

# Preview the production build
npm run preview
```

## Git workflow

Working directory matters here too. Most git operations run from any subfolder; the repo root contains both `Backend/` and `frontend/`.

```pwsh
git status
git diff
git log --oneline -10
```

Do not run destructive git commands (reset --hard, force push, branch -D) without explicit instruction.

## Environment variables (`.env` in `Backend/biat_testmanager/`)

Required for the app to boot:

```env
SECRET_KEY=...
FIELD_ENCRYPTION_KEY=...            # required for encrypted_model_fields (API keys)
DEBUG=True

DB_NAME=...
DB_USER=...
DB_PASSWORD=...
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

SPEC_EMBEDDING_MODEL_NAME=BAAI/bge-m3
SPEC_EMBEDDING_LOCAL_FILES_ONLY=True   # set False to allow HuggingFace downloads

MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_ARTIFACT_ROOT=file:///absolute/path/to/mlruns
MLFLOW_EXPERIMENT_NAME=biat-test-manager-specs
```

Optional AI:

```env
AI_GENERATION_ENABLE_CRITIC=False
AI_PLAYWRIGHT_MCP_COMMAND=npx
AI_PLAYWRIGHT_MCP_ARGS=["@playwright/mcp@latest", "--headless"]
AI_PLAYWRIGHT_MCP_START_TIMEOUT_SECONDS=45
AI_PLAYWRIGHT_MCP_CALL_TIMEOUT_SECONDS=30
AI_PLAYWRIGHT_MCP_LOG_FILE=  # optional path; if blank, MCP stderr goes to os.devnull
```

## Useful one-liners

```pwsh
# Verify Selenoid sees the registered browser images
curl http://localhost:4444/status

# List active Celery queues with details
uv run celery -A biat_testmanager inspect active_queues

# Purge a queue (dev only — destructive)
uv run celery -A biat_testmanager purge -Q ai_agent

# Tail MCP logs when AI_PLAYWRIGHT_MCP_LOG_FILE is set
Get-Content -Path <path> -Wait -Tail 50
```
