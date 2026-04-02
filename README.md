# BIAT Test Manager

BIAT Test Manager is a QA platform for managing specifications, designing tests, maintaining requirement traceability, and running browser automation from a single workspace.

The product is being built in layers:

- Layer 1: accounts and tenancy
- Layer 2: projects and membership
- Layer 3: specification ingestion, normalization, and RAG foundations
- Layer 4: manual qTest-like test design and requirement traceability
- Layer 5: automation and execution

The current focus is a strong manual-first QA product with clean execution foundations. AI and agent workflows are planned to sit on top of that foundation later.

## Current Capabilities

- Multi-tenant project structure with teams, projects, and project roles
- Specification ingestion from BA-owned source artifacts
- Normalized requirement records with project-level traceability
- Manual test design with `suite -> scenario -> test case`
- Requirement coverage at the test-case level
- Automation script storage and execution history
- Celery-backed execution pipeline with Playwright support in v1

## Current Layer 5 Status

Layer 5 is now partially implemented.

- Backend automation app exists
- `AutomationScript`, `TestExecution`, `ExecutionStep`, `TestResult`, `ExecutionSchedule`, and `HealingEvent` schema are implemented
- Celery + Redis execution flow is wired
- Only `Playwright` with `Python` scripts is runnable in v1
- `Selenium` exists in the schema but is not runnable yet
- Frontend includes a minimal automation section inside the project workspace test-case detail

## Architecture

### Backend

- Django + Django REST Framework
- PostgreSQL
- pgvector
- Celery
- Redis
- MLflow
- Playwright

Main backend apps:

- `accounts`
- `projects`
- `specs`
- `testing`
- `automation`

### Frontend

- Vite
- React
- TypeScript
- Tailwind CSS
- Zustand
- Axios

## Repository Layout

```text
BIAT-TestManager/
├─ Backend/
│  └─ biat_testmanager/
│     ├─ pyproject.toml
│     ├─ README.md
│     └─ src/
│        ├─ manage.py
│        ├─ biat_testmanager/
│        └─ apps/
│           ├─ accounts/
│           ├─ projects/
│           ├─ specs/
│           ├─ testing/
│           └─ automation/
├─ frontend/
│  ├─ package.json
│  ├─ README.md
│  └─ src/
└─ README.md
```

## Quick Start

### 1. Backend

See the backend guide in [Backend/biat_testmanager/README.md](Backend/biat_testmanager/README.md).

### 2. Frontend

See the frontend guide in [frontend/README.md](frontend/README.md).

## Local Runtime Overview

Typical local development uses three terminals:

1. Django API
2. Frontend Vite app
3. Celery worker

Redis is also required for async execution.

## Product Model

These distinctions matter in the codebase and in the UI:

- `SpecificationSource`: raw BA-owned source artifact
- `SpecificationSourceRecord`: parsed row or extracted source record
- `Specification`: normalized internal requirement
- `TestSuite -> TestScenario -> TestCase`: QA-owned manual test design layer
- `AutomationScript/TestExecution/...`: execution layer

## Important Limitations Right Now

- The frontend workspace is functional but still needs structural UX refinement
- Layer 5 UI is intentionally minimal for now
- Playwright execution is Python-only in v1
- No mature releases/cycles/runs dashboard yet
- AI generation and agent orchestration are not the current product focus

## Suggested Startup Order

1. Start PostgreSQL
2. Start Redis
3. Run Django migrations
4. Start Django server
5. Start Celery worker
6. Start the frontend app

## Team

- Project Lead: Wael Abid
- ML Engineer: Aziz Allah Barkaoui
- QA Engineer: Baccar Mihed
