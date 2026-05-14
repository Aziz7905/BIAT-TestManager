# Coding conventions

What this codebase already follows. New code should match — not generic advice, the actual patterns in this repo.

## Layered structure inside an app

```
apps/<app>/
├── models/<thing>.py        one file per model (or models.py if app is tiny — `ai/models.py` for example)
├── serializers/             DRF serializers; thin, declarative
├── services/                ALL business logic. Functions and dataclasses, no class hierarchies.
│   └── access.py            RBAC entry points (every mutating service calls one)
├── views/                   thin DRF views; call services, never inline logic
├── tasks.py                 Celery tasks; thin wrappers around service functions
├── urls.py                  route table for this app
├── migrations/              auto-generated; never hand-edit
└── tests/                   one test module per service area
```

Views never:
- Touch the ORM directly to mutate anything that has a service equivalent
- Import another app's models for cross-cutting writes — call that app's service instead
- Do permission checks themselves — services own that, called via `services/access.py`

## Service function signatures

Kwargs-first when the function takes more than one domain argument. Examples from the codebase:

```python
def create_test_case_with_revision(
    scenario,
    *,
    title: str,
    preconditions: str,
    steps: list,
    expected_result: str,
    test_data: dict,
    created_by=None,
) -> TestCase: ...

def start_browser_authoring_session(
    *,
    user,
    test_case,
    target_url: str,
    max_steps: int = MAX_AUTHORING_STEPS,
    browser: str = ExecutionBrowser.CHROMIUM,
    platform: str = ExecutionPlatform.DESKTOP,
) -> TestExecution: ...
```

This makes call sites readable and forces explicit naming of the "what".

## RBAC pattern

```python
from apps.<app>.services.access import can_<action>_<entity>

def some_service(user, entity, ...):
    if not can_<action>_<entity>(user, entity):
        raise PermissionError("...")
    # proceed
```

Every service that mutates or returns scoped data does this check. Views never check permissions inline — call the service and let it decide.

## Async / Celery enqueue pattern

```python
from django.db import transaction

def some_service(...):
    obj = Thing.objects.create(...)
    # enqueue AFTER commit so the worker sees the row
    transaction.on_commit(lambda: enqueue_task(str(obj.id)))
    return obj
```

`enqueue_task` itself wraps `.delay()` with an eager fallback for `DEBUG=True`. **Today's `enqueue_authoring_session_task` is NOT wrapped in `on_commit`** — Phase E Step 3 fixes that.

## Encrypted fields

Secrets (API keys, OAuth tokens, encrypted config JSON) use `django-encrypted-model-fields`:

```python
from encrypted_model_fields.fields import EncryptedCharField

class TeamAIConfig(models.Model):
    api_key = EncryptedCharField(max_length=512, null=True, blank=True)
```

Requires `FIELD_ENCRYPTION_KEY` in `.env`. Never log encrypted values raw.

## Audit / provenance pattern

When AI mutates canonical data, stash provenance in `source_snapshot_json`:

```python
update_test_case_with_revision(
    test_case,
    steps=...,
    design_status=TestCaseDesignStatus.DRAFT,
    created_by=user,
    source_snapshot_json={
        "mutation_source": "ai_browser_authoring_trace",   # always set
        "authoring_execution_id": str(execution.id),       # context
    },
)
```

Reviewers (and future debuggers) can grep for `mutation_source` to find AI-touched revisions.

## Channels event vocabulary

When publishing execution events, use the documented names so the frontend's `executionStore.mergeEvent` switch handles them:

- `execution.snapshot` — initial state
- `execution.status_changed`
- `execution.step_updated`
- `execution.result_ready`
- `execution.artifact_created`
- `execution.checkpoint_requested` / `checkpoint_resolved` / `checkpoint_expired`

Helpers live in `apps/automation/services/streaming.py` (`publish_execution_status_changed`, `publish_execution_step_updated`, etc.). Use them — do not write to the channel layer directly from services.

The Phase E live agent UX spec (`frontend/docs/architecture/05-ai-ux.md`) adds a richer event vocabulary (`agent_thought`, `agent_decision`, `agent_action_attempted`, `agent_action_result`, `agent_generated_step`, `agent_session_complete`) — not implemented yet.

## Test-writing pattern

- Tests live in `apps/<app>/tests/test_<area>.py`.
- Use `TransactionTestCase` only when needed (Channels, on_commit, lock testing); default to `TestCase` for speed.
- For LLM-touching code, use a `FakeProvider` / `FakeBrowserTool` injected via factory argument. The real provider/tool factories are passed as keyword args specifically to make this easy. See `apps/ai/tests/test_browser_authoring.py` for the pattern.
- Use `--keepdb` locally to skip DB setup on every run.
- Don't mock the database — integration tests should hit real Postgres (use the project test DB).

## Migration discipline

- One migration per logical change, not per session.
- After `makemigrations`, run `manage.py check` and `makemigrations --check --dry-run` to catch silently-skipped schema drift.
- Never hand-edit a migration that's already been applied in any environment.
- Adding a field that AI features write to — set a sensible default and add `null=True, blank=True` if needed to keep the migration backwards-compatible; backfill in a separate data migration if non-trivial.

## Settings flags

New behavior controlled by AI / experimental code should land behind a settings flag, **not** an env-var read scattered through code. Examples already in the repo:

- `AI_GENERATION_ENABLE_CRITIC` (bool, default False)
- `AI_PLAYWRIGHT_MCP_COMMAND` / `_ARGS` / `_START_TIMEOUT_SECONDS` / `_CALL_TIMEOUT_SECONDS` / `_LOG_FILE`
- `SPEC_EMBEDDING_LOCAL_FILES_ONLY`
- `AUTOMATION_RUNNER_DOCKER_NETWORK`

Read via `settings.<NAME>` only. Default in `settings.py` with `os.environ.get(...)` as the override source.

## What NOT to do

- **Do not refactor non-AI models** (testing / automation / specs / accounts / projects / integrations). They are stable and shared. AI is built *on top*.
- **Do not introduce a parallel test repository for AI drafts.** Drafts live on `AIGenerationSession.draft_payload`; canonical writes go through `commit_service`.
- **Do not call canonical write services directly from AI views** — go through `commit_service`.
- **Do not use Playwright in regression runners.** Runners have no Playwright installed. Layer 3 only.
- **Do not add `HealingEvent` back** until Phase F. The spec is preserved in `docs/backlog.md`.
- **Do not bypass `IntegrationResolverService`** when reaching Jira / GitHub / Jenkins. Even AI agents go through it (act_as_app vs act_as_user).
- **Do not send full DOM / huge MCP snapshots to the LLM.** Compact at the call site, not at the tool — the tool's full snapshot is still recorded for save-trace.
- **Do not leak API keys to LLM prompts or logs.** Encrypted fields stay encrypted in logs.
- **Do not skip `transaction.on_commit` for Celery enqueues** in any new code path that may end up inside an `atomic()` block.

## Naming conventions

- Files: `snake_case.py`.
- Models: `PascalCase` (singular).
- Functions / variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Service function naming reflects intent: `create_…`, `update_…`, `start_…`, `enqueue_…`, `save_…`, `cancel_…`, `apply_…`.
- RBAC functions: `can_<action>_<entity>(user, entity) -> bool`.
- Channels publish helpers: `publish_<event_name>(payload)`.
- Celery task names: `<app>.<verb_phrase>` (e.g. `ai.run_authoring_session`).
- Prompt version constants: `<name>_PROMPT_VERSION = "<slug>_v1"`. Schema versions follow the same `_v1` pattern.

## Docstring discipline

- Module-level: optional, only when the module's purpose isn't obvious from filename + content.
- Function docstrings: short (1-2 lines) when the function name + signature already describes the contract. Longer docstrings only when there's a non-obvious invariant or side effect to flag.
- No `# noqa`, no `# type: ignore` without a reason in the same comment.
